"""
Isaac Lab with Meta Quest Hand Tracking - Advanced Version
高级版本，支持配置文件、平滑滤波、多对象交互等功能
"""

import numpy as np
import torch
from omni.isaac.lab.app import AppLauncher
import configparser
from pathlib import Path
from collections import deque

# 启动配置
app_launcher = AppLauncher(headless=False)
simulation_app = app_launcher.app

import omni.isaac.lab.sim as sim_utils
from omni.isaac.lab.assets import RigidObject, RigidObjectCfg
from omni.isaac.lab.scene import InteractiveScene, InteractiveSceneCfg
from omni.isaac.lab.sim import SimulationContext
from omni.isaac.lab.utils import configclass

import socket
import json
import threading
import time
from dataclasses import dataclass
from typing import Optional, List, Tuple


class Config:
    """配置管理器"""
    
    def __init__(self, config_file='config.ini'):
        self.config = configparser.ConfigParser(
            inline_comment_prefixes=("#", ";")
        )
        
        # 如果配置文件不存在,使用默认值
        if Path(config_file).exists():
            self.config.read(config_file)
        else:
            self._set_defaults()
    
    def _set_defaults(self):
        """设置默认配置"""
        self.config['network'] = {
            'host': '0.0.0.0',
            'port': '8888',
            'timeout': '0.1'
        }
        self.config['tracking'] = {
            'update_rate': '60',
            'position_scale': '2.0',
            'position_offset_x': '0.5',
            'position_offset_y': '0.0',
            'position_offset_z': '0.5'
        }
        self.config['grasping'] = {
            'pinch_threshold': '0.6',
            'grasp_distance': '0.15',
            'release_delay': '0.1'
        }
        self.config['visualization'] = {
            'show_debug_info': 'true',
            'debug_print_interval': '100'
        }
        self.config['advanced'] = {
            'enable_position_smoothing': 'true',
            'smoothing_factor': '0.3',
            'enable_prediction': 'false'
        }
    
    def get(self, section, key, fallback=None):
        """获取配置值"""
        return self.config.get(section, key, fallback=fallback)
    
    def getfloat(self, section, key, fallback=0.0):
        """获取浮点数配置"""
        return self.config.getfloat(section, key, fallback=fallback)
    
    def getint(self, section, key, fallback=0):
        """获取整数配置"""
        return self.config.getint(section, key, fallback=fallback)
    
    def getboolean(self, section, key, fallback=False):
        """获取布尔值配置"""
        return self.config.getboolean(section, key, fallback=fallback)


@dataclass
class HandTrackingData:
    """手部追踪数据结构"""
    position: np.ndarray
    rotation: np.ndarray
    pinch_strength: float
    is_tracking: bool
    velocity: np.ndarray  # 新增: 速度
    timestamp: float  # 新增: 时间戳
    
    def __init__(self):
        self.position = np.zeros(3)
        self.rotation = np.array([1.0, 0.0, 0.0, 0.0])
        self.pinch_strength = 0.0
        self.is_tracking = False
        self.velocity = np.zeros(3)
        self.timestamp = 0.0


class PositionSmoother:
    """位置平滑滤波器"""
    
    def __init__(self, window_size=5, alpha=0.3):
        self.window_size = window_size
        self.alpha = alpha  # 指数移动平均系数
        self.position_history = deque(maxlen=window_size)
        self.smoothed_position = None
    
    def update(self, position: np.ndarray) -> np.ndarray:
        """更新并返回平滑后的位置"""
        self.position_history.append(position)
        
        if self.smoothed_position is None:
            self.smoothed_position = position
        else:
            # 指数移动平均
            self.smoothed_position = (self.alpha * position + 
                                     (1 - self.alpha) * self.smoothed_position)
        
        return self.smoothed_position.copy()
    
    def reset(self):
        """重置滤波器"""
        self.position_history.clear()
        self.smoothed_position = None


class VisionProReceiver:
    """增强版 Meta Quest 数据接收器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.host = config.get('network', 'host', fallback='0.0.0.0')
        self.port = config.getint('network', 'port', fallback=8888)
        self.timeout = config.getfloat('network', 'timeout', fallback=0.1)
        self.update_rate = max(config.getfloat('tracking', 'update_rate', fallback=60.0), 1.0)
        self.expected_dt = 1.0 / self.update_rate
        self.tracking_stale_timeout = max(self.timeout * 2.0, self.expected_dt * 6.0)
        self.ack_interval = max(self.expected_dt, 0.25)
        
        self.left_hand = HandTrackingData()
        self.right_hand = HandTrackingData()
        self.data_lock = threading.Lock()
        
        # 平滑滤波器
        if config.getboolean('advanced', 'enable_position_smoothing', fallback=True):
            smoothing_factor = config.getfloat('advanced', 'smoothing_factor', fallback=0.3)
            self.left_smoother = PositionSmoother(alpha=smoothing_factor)
            self.right_smoother = PositionSmoother(alpha=smoothing_factor)
        else:
            self.left_smoother = None
            self.right_smoother = None
        
        self.running = False
        self.thread = None
        self.socket = None
        
        # 统计信息
        self.packets_received = 0
        self.packets_dropped = 0
        self.left_last_received_monotonic = 0.0
        self.right_last_received_monotonic = 0.0
        self.last_ack_monotonic = 0.0
        
    def start(self):
        """启动接收线程"""
        self.running = True
        self.thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.thread.start()
        print(f"✓ Meta Quest receiver started on {self.host}:{self.port}")
        
    def stop(self):
        """停止接收"""
        self.running = False
        if self.socket:
            self.socket.close()
        if self.thread:
            self.thread.join()
        print(f"Meta Quest receiver stopped. Packets: {self.packets_received}, Dropped: {self.packets_dropped}")
            
    def _receive_loop(self):
        """接收数据循环"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.host, self.port))
        self.socket.settimeout(self.timeout)
        
        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                self._parse_data(data, addr)
                self.packets_received += 1
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Error receiving data: {e}")
                    self.packets_dropped += 1
                else:
                    break
                
    def _copy_hand_data(self, hand_data: HandTrackingData) -> HandTrackingData:
        copied = HandTrackingData()
        copied.position = hand_data.position.copy()
        copied.rotation = hand_data.rotation.copy()
        copied.pinch_strength = hand_data.pinch_strength
        copied.is_tracking = hand_data.is_tracking
        copied.velocity = hand_data.velocity.copy()
        copied.timestamp = hand_data.timestamp
        return copied

    def get_hand_snapshots(self) -> Tuple[HandTrackingData, HandTrackingData]:
        """返回线程安全的手部数据快照"""
        self.refresh_tracking_state()

        with self.data_lock:
            return (
                self._copy_hand_data(self.left_hand),
                self._copy_hand_data(self.right_hand),
            )

    def refresh_tracking_state(self):
        """如果长时间没有收到新包，则将追踪状态标为失效"""
        now = time.monotonic()

        with self.data_lock:
            if (self.left_hand.is_tracking and self.left_last_received_monotonic > 0.0 and
                    now - self.left_last_received_monotonic > self.tracking_stale_timeout):
                self.left_hand.is_tracking = False
                self.left_hand.velocity = np.zeros(3)
                self.left_hand.pinch_strength = 0.0

            if (self.right_hand.is_tracking and self.right_last_received_monotonic > 0.0 and
                    now - self.right_last_received_monotonic > self.tracking_stale_timeout):
                self.right_hand.is_tracking = False
                self.right_hand.velocity = np.zeros(3)
                self.right_hand.pinch_strength = 0.0

    def _send_ack(self, addr):
        """向Quest发送应用层ACK，供UI判断远端是否真的在线"""
        if self.socket is None:
            return

        payload = {
            "type": "ack",
            "server_status": "listening",
            "server_time": time.time(),
            "packets_received": self.packets_received,
        }

        try:
            self.socket.sendto(json.dumps(payload).encode("utf-8"), addr)
        except OSError:
            # 套接字关闭或地址不可达时忽略，等待下一次有效数据包。
            pass

    def _parse_data(self, data: bytes, addr):
        """解析接收到的JSON数据"""
        try:
            json_data = json.loads(data.decode('utf-8'))
            current_time = float(json_data.get('timestamp', 0.0))
            now_monotonic = time.monotonic()
            should_send_ack = False
            
            with self.data_lock:
                # 解析左手数据
                if 'left_hand' in json_data:
                    left = json_data['left_hand']
                    raw_position = np.array(left.get('position', [0, 0, 0]), dtype=np.float64)
                    
                    # 应用平滑滤波
                    if self.left_smoother:
                        position = self.left_smoother.update(raw_position)
                    else:
                        position = raw_position
                    
                    previous_position = self.left_hand.position.copy()
                    previous_timestamp = self.left_hand.timestamp
                    dt = current_time - previous_timestamp if previous_timestamp > 0.0 else self.expected_dt
                    if dt <= 0.0:
                        dt = self.expected_dt

                    velocity = (position - previous_position) / dt
                    is_tracking = left.get('is_tracking', False)

                    self.left_hand.position = position
                    self.left_hand.rotation = np.array(left.get('rotation', [1, 0, 0, 0]), dtype=np.float64)
                    self.left_hand.pinch_strength = left.get('pinch_strength', 0.0)
                    self.left_hand.is_tracking = is_tracking
                    self.left_hand.velocity = velocity if is_tracking else np.zeros(3)
                    self.left_hand.timestamp = current_time
                    self.left_last_received_monotonic = now_monotonic
                
                # 解析右手数据
                if 'right_hand' in json_data:
                    right = json_data['right_hand']
                    raw_position = np.array(right.get('position', [0, 0, 0]), dtype=np.float64)
                    
                    if self.right_smoother:
                        position = self.right_smoother.update(raw_position)
                    else:
                        position = raw_position
                    
                    previous_position = self.right_hand.position.copy()
                    previous_timestamp = self.right_hand.timestamp
                    dt = current_time - previous_timestamp if previous_timestamp > 0.0 else self.expected_dt
                    if dt <= 0.0:
                        dt = self.expected_dt

                    velocity = (position - previous_position) / dt
                    is_tracking = right.get('is_tracking', False)
                    
                    self.right_hand.position = position
                    self.right_hand.rotation = np.array(right.get('rotation', [1, 0, 0, 0]), dtype=np.float64)
                    self.right_hand.pinch_strength = right.get('pinch_strength', 0.0)
                    self.right_hand.is_tracking = is_tracking
                    self.right_hand.velocity = velocity if is_tracking else np.zeros(3)
                    self.right_hand.timestamp = current_time
                    self.right_last_received_monotonic = now_monotonic

                if now_monotonic - self.last_ack_monotonic >= self.ack_interval:
                    self.last_ack_monotonic = now_monotonic
                    should_send_ack = True

            if should_send_ack:
                self._send_ack(addr)
                
        except Exception as e:
            print(f"Error parsing data: {e}")


@configclass
class VirtualHandSceneCfg(InteractiveSceneCfg):
    """场景配置"""
    
    ground = sim_utils.GroundPlaneCfg()
    
    dome_light = sim_utils.DomeLightCfg(
        intensity=3000.0,
        color=(0.75, 0.75, 0.75)
    )
    
    left_hand: RigidObjectCfg = RigidObjectCfg(
        prim_path="/World/LeftHand",
        spawn=sim_utils.CuboidCfg(
            size=(0.08, 0.04, 0.15),
            rigid_props=sim_utils.RigidBodyPropertiesCfg(kinematic_enabled=True),
            mass_props=sim_utils.MassPropertiesCfg(mass=0.5),
            collision_props=sim_utils.CollisionPropertiesCfg(),
            visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.2, 0.6, 0.8)),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=(0.3, 0.3, 0.5)),
    )
    
    right_hand: RigidObjectCfg = RigidObjectCfg(
        prim_path="/World/RightHand",
        spawn=sim_utils.CuboidCfg(
            size=(0.08, 0.04, 0.15),
            rigid_props=sim_utils.RigidBodyPropertiesCfg(kinematic_enabled=True),
            mass_props=sim_utils.MassPropertiesCfg(mass=0.5),
            collision_props=sim_utils.CollisionPropertiesCfg(),
            visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.8, 0.6, 0.2)),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=(0.3, -0.3, 0.5)),
    )
    
    # 多个可操控对象
    cube: RigidObjectCfg = RigidObjectCfg(
        prim_path="/World/Cube",
        spawn=sim_utils.CuboidCfg(
            size=(0.1, 0.1, 0.1),
            rigid_props=sim_utils.RigidBodyPropertiesCfg(),
            mass_props=sim_utils.MassPropertiesCfg(mass=0.5),
            collision_props=sim_utils.CollisionPropertiesCfg(),
            visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.8, 0.2, 0.2)),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=(0.5, 0.0, 0.3)),
    )
    
    sphere: RigidObjectCfg = RigidObjectCfg(
        prim_path="/World/Sphere",
        spawn=sim_utils.SphereCfg(
            radius=0.06,
            rigid_props=sim_utils.RigidBodyPropertiesCfg(),
            mass_props=sim_utils.MassPropertiesCfg(mass=0.3),
            collision_props=sim_utils.CollisionPropertiesCfg(),
            visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.2, 0.8, 0.2)),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=(0.7, 0.2, 0.3)),
    )
    
    cylinder: RigidObjectCfg = RigidObjectCfg(
        prim_path="/World/Cylinder",
        spawn=sim_utils.CylinderCfg(
            radius=0.05,
            height=0.15,
            rigid_props=sim_utils.RigidBodyPropertiesCfg(),
            mass_props=sim_utils.MassPropertiesCfg(mass=0.4),
            collision_props=sim_utils.CollisionPropertiesCfg(),
            visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.2, 0.2, 0.8)),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=(0.6, -0.2, 0.3)),
    )


class VirtualHandController:
    """增强版虚拟手控制器"""
    
    def __init__(self, scene: InteractiveScene, visionpro: VisionProReceiver, config: Config):
        self.scene = scene
        self.visionpro = visionpro
        self.config = config
        
        self.left_hand = scene["left_hand"]
        self.right_hand = scene["right_hand"]
        self.objects = [scene["cube"], scene["sphere"], scene["cylinder"]]
        
        # 抓取状态
        self.left_grasped_object = None
        self.right_grasped_object = None
        self.left_grasp_offset = np.zeros(3)
        self.right_grasp_offset = np.zeros(3)
        self.left_release_elapsed = 0.0
        self.right_release_elapsed = 0.0
        
        # 参数
        self.grasp_threshold = config.getfloat('grasping', 'pinch_threshold', fallback=0.6)
        self.grasp_distance = config.getfloat('grasping', 'grasp_distance', fallback=0.15)
        self.release_delay = config.getfloat('grasping', 'release_delay', fallback=0.1)
        
        # 坐标转换
        self.scale = config.getfloat('tracking', 'position_scale', fallback=2.0)
        self.offset = np.array([
            config.getfloat('tracking', 'position_offset_x', fallback=0.5),
            config.getfloat('tracking', 'position_offset_y', fallback=0.0),
            config.getfloat('tracking', 'position_offset_z', fallback=0.5)
        ])
        self.enable_prediction = config.getboolean('advanced', 'enable_prediction', fallback=False)
        self.prediction_time = config.getfloat('advanced', 'prediction_time', fallback=0.05)
        
    def update(self, dt: float):
        """更新虚拟手状态"""
        left_hand_data, right_hand_data = self.visionpro.get_hand_snapshots()

        if left_hand_data.is_tracking:
            self._update_hand(self.left_hand, left_hand_data, "left", dt)
        
        if right_hand_data.is_tracking:
            self._update_hand(self.right_hand, right_hand_data, "right", dt)
            
    def _update_hand(self, hand_object: RigidObject, hand_data: HandTrackingData, hand_type: str, dt: float):
        """更新单个手的状态"""
        source_position = hand_data.position
        if self.enable_prediction:
            source_position = source_position + hand_data.velocity * self.prediction_time

        position = source_position * self.scale + self.offset
        rotation = hand_data.rotation
        
        hand_object.write_root_pose_to_sim(
            torch.tensor([position], dtype=torch.float32, device=hand_object.device),
            torch.tensor([rotation], dtype=torch.float32, device=hand_object.device)
        )
        
        self._handle_grasping(hand_object, hand_data, hand_type, position, dt)
        
    def _handle_grasping(self, hand_object: RigidObject, hand_data: HandTrackingData, 
                        hand_type: str, hand_pos: np.ndarray, dt: float):
        """处理抓取逻辑"""
        is_pinching = hand_data.pinch_strength > self.grasp_threshold
        
        if hand_type == "left":
            grasped_obj = self.left_grasped_object
            grasp_offset = self.left_grasp_offset
            release_elapsed = self.left_release_elapsed
        else:
            grasped_obj = self.right_grasped_object
            grasp_offset = self.right_grasp_offset
            release_elapsed = self.right_release_elapsed
        release_state_written = False

        if is_pinching:
            release_elapsed = 0.0
        elif grasped_obj is not None:
            release_elapsed += dt
        else:
            release_elapsed = 0.0
        
        if is_pinching and grasped_obj is None:
            # 尝试抓取
            closest_obj = None
            min_distance = self.grasp_distance
            
            for obj in self.objects:
                # 避免双手同时抓取同一个对象，后更新的手会覆盖前一只手的控制。
                if hand_type == "left" and obj is self.right_grasped_object:
                    continue
                if hand_type == "right" and obj is self.left_grasped_object:
                    continue

                obj_pos = obj.data.root_pos_w[0].cpu().numpy()
                distance = np.linalg.norm(hand_pos - obj_pos)
                
                if distance < min_distance:
                    min_distance = distance
                    closest_obj = obj
            
            if closest_obj is not None:
                # 抓取物体
                obj_pos = closest_obj.data.root_pos_w[0].cpu().numpy()
                offset = obj_pos - hand_pos
                
                if hand_type == "left":
                    self.left_grasped_object = closest_obj
                    self.left_grasp_offset = offset
                    self.left_release_elapsed = 0.0
                else:
                    self.right_grasped_object = closest_obj
                    self.right_grasp_offset = offset
                    self.right_release_elapsed = 0.0
                release_state_written = True
                
                print(f"✓ {hand_type} hand grasped {closest_obj.cfg.prim_path}")
                    
        elif grasped_obj is not None and not is_pinching and release_elapsed >= self.release_delay:
            # 释放物体
            if hand_type == "left":
                self.left_grasped_object = None
                self.left_release_elapsed = 0.0
            else:
                self.right_grasped_object = None
                self.right_release_elapsed = 0.0
            release_state_written = True
            print(f"✓ {hand_type} hand released {grasped_obj.cfg.prim_path}")
            
        elif grasped_obj is not None:
            # 保持抓取，或在release_delay窗口内继续跟随手移动。
            target_pos = hand_pos + grasp_offset
            grasped_obj.write_root_pose_to_sim(
                torch.tensor([target_pos], dtype=torch.float32, device=grasped_obj.device),
                grasped_obj.data.root_quat_w
            )

            if hand_type == "left":
                self.left_release_elapsed = release_elapsed
            else:
                self.right_release_elapsed = release_elapsed
            release_state_written = True

        if not release_state_written:
            if hand_type == "left":
                self.left_release_elapsed = release_elapsed
            else:
                self.right_release_elapsed = release_elapsed


def configure_simulation_timing(sim: SimulationContext, config: Config) -> Tuple[float, float]:
    """尽量将config中的physics_dt/render_dt应用到Isaac仿真上下文"""
    configured_physics_dt = config.getfloat('performance', 'physics_dt', fallback=sim.get_physics_dt())
    configured_render_dt = config.getfloat('performance', 'render_dt', fallback=configured_physics_dt)

    applied = False
    setters = [
        ("set_simulation_dt", (), {"physics_dt": configured_physics_dt, "rendering_dt": configured_render_dt}),
        ("set_simulation_dt", (configured_physics_dt, configured_render_dt), {}),
        ("set_dt", (), {"physics_dt": configured_physics_dt, "rendering_dt": configured_render_dt}),
        ("set_dt", (configured_physics_dt, configured_render_dt), {}),
    ]

    for method_name, args, kwargs in setters:
        method = getattr(sim, method_name, None)
        if method is None:
            continue

        try:
            method(*args, **kwargs)
            applied = True
            break
        except TypeError:
            continue

    if not applied:
        print("Warning: unable to apply physics_dt/render_dt from config to SimulationContext; using runtime defaults.")
        configured_physics_dt = sim.get_physics_dt()

    return configured_physics_dt, configured_render_dt


def main():
    """主函数"""
    # 加载配置
    config = Config('config.ini')
    
    # 创建场景
    scene_cfg = VirtualHandSceneCfg(
        num_envs=config.getint('scene', 'num_envs', fallback=1),
        env_spacing=config.getfloat('scene', 'env_spacing', fallback=2.0),
    )
    scene = InteractiveScene(scene_cfg)
    
    # 初始化 Meta Quest 接收器
    visionpro = VisionProReceiver(config)
    visionpro.start()
    
    # 创建虚拟手控制器
    controller = VirtualHandController(scene, visionpro, config)
    
    # 获取仿真上下文
    sim = SimulationContext.instance()
    sim_dt, render_dt = configure_simulation_timing(sim, config)
    
    print("\n" + "="*80)
    print("Isaac Lab Virtual Hand Control - Advanced")
    print("="*80)
    print("\n配置:")
    print(f"  服务器: {config.get('network', 'host')}:{config.get('network', 'port')}")
    print(f"  抓取阈值: {config.getfloat('grasping', 'pinch_threshold')}")
    print(f"  释放延迟: {config.getfloat('grasping', 'release_delay'):.2f}s")
    print(f"  平滑滤波: {'启用' if config.getboolean('advanced', 'enable_position_smoothing') else '禁用'}")
    print(f"  位置预测: {'启用' if config.getboolean('advanced', 'enable_prediction') else '禁用'}")
    print(f"  update_rate: {config.getfloat('tracking', 'update_rate'):.0f} Hz")
    print(f"  num_envs: {config.getint('scene', 'num_envs')} | env_spacing: {config.getfloat('scene', 'env_spacing')}")
    print(f"  physics_dt: {sim_dt:.4f} | render_dt: {render_dt:.4f}")
    print("\n正在等待 Meta Quest 连接...")
    print("="*80 + "\n")
    
    # 主循环
    try:
        count = 0
        show_debug = config.getboolean('visualization', 'show_debug_info', fallback=True)
        debug_interval = config.getint('visualization', 'debug_print_interval', fallback=100)
        scene.reset()
        
        while simulation_app.is_running():
            controller.update(sim_dt)
            scene.write_data_to_sim()
            sim.step()
            scene.update(sim_dt)
            
            count += 1
            
            if show_debug and count % debug_interval == 0:
                left_hand_data, right_hand_data = visionpro.get_hand_snapshots()
                left_status = "✓" if left_hand_data.is_tracking else "✗"
                right_status = "✓" if right_hand_data.is_tracking else "✗"
                print(f"[Frame {count}] L:{left_status} R:{right_status} | "
                      f"Packets: {visionpro.packets_received}")
            
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    finally:
        visionpro.stop()
        simulation_app.close()


if __name__ == "__main__":
    main()

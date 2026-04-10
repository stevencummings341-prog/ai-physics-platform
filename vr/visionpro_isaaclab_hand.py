"""
Isaac Lab with Meta Quest Hand Tracking
使用 Meta Quest 手部追踪在 Isaac Lab 中控制虚拟手
"""

import numpy as np
import torch
from omni.isaac.lab.app import AppLauncher

# 启动配置
app_launcher = AppLauncher(headless=False)
simulation_app = app_launcher.app

import omni.isaac.lab.sim as sim_utils
from omni.isaac.lab.assets import RigidObject, RigidObjectCfg
from omni.isaac.lab.scene import InteractiveScene, InteractiveSceneCfg
from omni.isaac.lab.sim import SimulationContext
from omni.isaac.lab.utils import configclass
from omni.isaac.lab.controllers import DifferentialIKController, DifferentialIKControllerCfg
from omni.isaac.lab.managers import SceneEntityCfg

import socket
import json
import threading
from dataclasses import dataclass
from typing import Optional


@dataclass
class HandTrackingData:
    """手部追踪数据结构"""
    position: np.ndarray  # 手掌位置 [x, y, z]
    rotation: np.ndarray  # 手掌旋转 (四元数) [w, x, y, z]
    pinch_strength: float  # 捏合强度 (0-1)
    is_tracking: bool  # 是否正在追踪
    
    def __init__(self):
        self.position = np.zeros(3)
        self.rotation = np.array([1.0, 0.0, 0.0, 0.0])
        self.pinch_strength = 0.0
        self.is_tracking = False


class VisionProReceiver:
    """接收 Meta Quest 手部追踪数据的服务器"""
    
    def __init__(self, host='0.0.0.0', port=8888):
        self.host = host
        self.port = port
        self.left_hand = HandTrackingData()
        self.right_hand = HandTrackingData()
        self.running = False
        self.thread = None
        self.socket = None
        
    def start(self):
        """启动接收线程"""
        self.running = True
        self.thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.thread.start()
        print(f"Meta Quest receiver started on {self.host}:{self.port}")
        
    def stop(self):
        """停止接收"""
        self.running = False
        if self.socket:
            self.socket.close()
        if self.thread:
            self.thread.join()
            
    def _receive_loop(self):
        """接收数据循环"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.host, self.port))
        self.socket.settimeout(0.1)
        
        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                self._parse_data(data)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Error receiving data: {e}")
                else:
                    break
                
    def _parse_data(self, data: bytes):
        """解析接收到的JSON数据"""
        try:
            json_data = json.loads(data.decode('utf-8'))
            
            # 解析左手数据
            if 'left_hand' in json_data:
                left = json_data['left_hand']
                self.left_hand.position = np.array(left.get('position', [0, 0, 0]))
                self.left_hand.rotation = np.array(left.get('rotation', [1, 0, 0, 0]))
                self.left_hand.pinch_strength = left.get('pinch_strength', 0.0)
                self.left_hand.is_tracking = left.get('is_tracking', False)
            
            # 解析右手数据
            if 'right_hand' in json_data:
                right = json_data['right_hand']
                self.right_hand.position = np.array(right.get('position', [0, 0, 0]))
                self.right_hand.rotation = np.array(right.get('rotation', [1, 0, 0, 0]))
                self.right_hand.pinch_strength = right.get('pinch_strength', 0.0)
                self.right_hand.is_tracking = right.get('is_tracking', False)
                
        except Exception as e:
            print(f"Error parsing data: {e}")


@configclass
class VirtualHandSceneCfg(InteractiveSceneCfg):
    """场景配置"""
    
    # 地面
    ground = sim_utils.GroundPlaneCfg()
    
    # 光照
    dome_light = sim_utils.DomeLightCfg(
        intensity=3000.0,
        color=(0.75, 0.75, 0.75)
    )
    
    # 虚拟手 (使用简单的几何体表示)
    left_hand: RigidObjectCfg = RigidObjectCfg(
        prim_path="/World/LeftHand",
        spawn=sim_utils.CuboidCfg(
            size=(0.08, 0.04, 0.15),
            rigid_props=sim_utils.RigidBodyPropertiesCfg(
                kinematic_enabled=True,
            ),
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
            rigid_props=sim_utils.RigidBodyPropertiesCfg(
                kinematic_enabled=True,
            ),
            mass_props=sim_utils.MassPropertiesCfg(mass=0.5),
            collision_props=sim_utils.CollisionPropertiesCfg(),
            visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.8, 0.6, 0.2)),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=(0.3, -0.3, 0.5)),
    )
    
    # 可操控的物体
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


class VirtualHandController:
    """虚拟手控制器"""
    
    def __init__(self, scene: InteractiveScene, visionpro: VisionProReceiver):
        self.scene = scene
        self.visionpro = visionpro
        
        # 获取场景对象
        self.left_hand = scene["left_hand"]
        self.right_hand = scene["right_hand"]
        self.objects = [scene["cube"], scene["sphere"]]
        
        # 抓取状态
        self.left_grasped_object = None
        self.right_grasped_object = None
        self.grasp_threshold = 0.6  # 捏合阈值
        self.grasp_distance = 0.15  # 抓取距离阈值
        
        # 坐标转换参数 (Meta Quest -> Isaac Lab)
        self.scale = 2.0  # 缩放因子
        self.offset = np.array([0.5, 0.0, 0.5])  # 位置偏移
        
    def update(self, dt: float):
        """更新虚拟手状态"""
        # 更新左手
        if self.visionpro.left_hand.is_tracking:
            self._update_hand(
                self.left_hand,
                self.visionpro.left_hand,
                "left"
            )
        
        # 更新右手
        if self.visionpro.right_hand.is_tracking:
            self._update_hand(
                self.right_hand,
                self.visionpro.right_hand,
                "right"
            )
            
    def _update_hand(self, hand_object: RigidObject, hand_data: HandTrackingData, hand_type: str):
        """更新单个手的状态"""
        # 转换位置 (Meta Quest 坐标 -> Isaac Lab 坐标)
        position = hand_data.position * self.scale + self.offset
        
        # 转换旋转 (四元数格式: w,x,y,z)
        rotation = hand_data.rotation
        
        # 设置手的位置和旋转
        hand_object.write_root_pose_to_sim(
            torch.tensor([position], dtype=torch.float32, device=hand_object.device),
            torch.tensor([rotation], dtype=torch.float32, device=hand_object.device)
        )
        
        # 处理抓取逻辑
        self._handle_grasping(hand_object, hand_data, hand_type)
        
    def _handle_grasping(self, hand_object: RigidObject, hand_data: HandTrackingData, hand_type: str):
        """处理抓取逻辑"""
        is_pinching = hand_data.pinch_strength > self.grasp_threshold
        
        if hand_type == "left":
            grasped_obj = self.left_grasped_object
        else:
            grasped_obj = self.right_grasped_object
        
        hand_pos = hand_object.data.root_pos_w[0].cpu().numpy()
        
        if is_pinching and grasped_obj is None:
            # 尝试抓取物体
            for obj in self.objects:
                if hand_type == "left" and obj is self.right_grasped_object:
                    continue
                if hand_type == "right" and obj is self.left_grasped_object:
                    continue

                obj_pos = obj.data.root_pos_w[0].cpu().numpy()
                distance = np.linalg.norm(hand_pos - obj_pos)
                
                if distance < self.grasp_distance:
                    # 抓取物体
                    if hand_type == "left":
                        self.left_grasped_object = obj
                    else:
                        self.right_grasped_object = obj
                    print(f"{hand_type} hand grasped object at distance {distance:.3f}")
                    break
                    
        elif not is_pinching and grasped_obj is not None:
            # 释放物体
            if hand_type == "left":
                self.left_grasped_object = None
            else:
                self.right_grasped_object = None
            print(f"{hand_type} hand released object")
            
        elif is_pinching and grasped_obj is not None:
            # 移动被抓取的物体
            grasped_obj.write_root_pose_to_sim(
                torch.tensor([hand_pos], dtype=torch.float32, device=grasped_obj.device),
                grasped_obj.data.root_quat_w
            )


def main():
    """主函数"""
    # 创建场景配置
    scene_cfg = VirtualHandSceneCfg(num_envs=1, env_spacing=2.0)
    
    # 创建场景
    scene = InteractiveScene(scene_cfg)
    
    # 初始化 Meta Quest 接收器
    visionpro = VisionProReceiver(host='0.0.0.0', port=8888)
    visionpro.start()
    
    # 创建虚拟手控制器
    controller = VirtualHandController(scene, visionpro)
    
    # 获取仿真上下文
    sim = SimulationContext.instance()
    
    print("\n" + "="*80)
    print("Isaac Lab Virtual Hand Control with Meta Quest")
    print("="*80)
    print("\n使用说明:")
    print("1. 在 Meta Quest 上运行配套的手部追踪应用")
    print("2. 应用会将手部数据发送到端口 8888")
    print("3. 使用捏合手势 (pinch) 来抓取和移动物体")
    print("4. 左手显示为蓝色,右手显示为橙色")
    print("5. 按 Ctrl+C 退出")
    print("\n正在等待 Meta Quest 连接...")
    print("="*80 + "\n")
    
    # 主循环
    try:
        sim_dt = sim.get_physics_dt()
        count = 0
        scene.reset()
        
        while simulation_app.is_running():
            # 更新虚拟手
            controller.update(sim_dt)
            
            # 写入数据到仿真
            scene.write_data_to_sim()
            
            # 步进仿真
            sim.step()
            
            # 更新场景状态
            scene.update(sim_dt)
            
            count += 1
            
            # 显示追踪状态
            if count % 100 == 0:
                left_tracking = "✓" if visionpro.left_hand.is_tracking else "✗"
                right_tracking = "✓" if visionpro.right_hand.is_tracking else "✗"
                print(f"追踪状态 - 左手: {left_tracking} | 右手: {right_tracking} | "
                      f"左手捏合: {visionpro.left_hand.pinch_strength:.2f} | "
                      f"右手捏合: {visionpro.right_hand.pinch_strength:.2f}")
            
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    finally:
        visionpro.stop()
        simulation_app.close()


if __name__ == "__main__":
    main()

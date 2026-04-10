"""
Meta Quest Hand Tracking Simulator
用于测试 Isaac Lab 虚拟手系统，无需真实的 Meta Quest 设备
"""

import socket
import json
import time
import numpy as np
import argparse


class HandTrackingSimulator:
    """模拟 Meta Quest 手部追踪数据"""
    
    def __init__(self, host='127.0.0.1', port=8888, fps=60):
        self.host = host
        self.port = port
        self.fps = fps
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # 模拟参数
        self.time = 0.0
        self.dt = 1.0 / fps
        
        # 手部初始位置
        self.left_center = np.array([0.15, 0.15, 0.0])
        self.right_center = np.array([0.15, -0.15, 0.0])
        
        # 运动模式
        self.mode = "circle"  # "circle", "wave", "grab"
        
    def generate_hand_data(self):
        """生成模拟的手部追踪数据"""
        self.time += self.dt
        
        # 根据不同模式生成数据
        if self.mode == "circle":
            data = self._generate_circle_motion()
        elif self.mode == "wave":
            data = self._generate_wave_motion()
        elif self.mode == "grab":
            data = self._generate_grab_motion()
        else:
            data = self._generate_static_data()
            
        return data
    
    def _generate_circle_motion(self):
        """生成圆周运动"""
        # 左手顺时针圆周运动
        angle_left = self.time * 0.5
        radius = 0.1
        left_pos = self.left_center + np.array([
            radius * np.cos(angle_left),
            radius * np.sin(angle_left),
            0.05 * np.sin(angle_left * 2)
        ])
        
        # 右手逆时针圆周运动
        angle_right = -self.time * 0.5
        right_pos = self.right_center + np.array([
            radius * np.cos(angle_right),
            radius * np.sin(angle_right),
            0.05 * np.sin(angle_right * 2)
        ])
        
        # 周期性的捏合动作
        left_pinch = 0.5 + 0.5 * np.sin(self.time * 2)
        right_pinch = 0.5 + 0.5 * np.sin(self.time * 2 + np.pi)
        
        return {
            'left_hand': {
                'position': left_pos.tolist(),
                'rotation': [1.0, 0.0, 0.0, 0.0],
                'pinch_strength': float(left_pinch),
                'is_tracking': True
            },
            'right_hand': {
                'position': right_pos.tolist(),
                'rotation': [1.0, 0.0, 0.0, 0.0],
                'pinch_strength': float(right_pinch),
                'is_tracking': True
            },
            'timestamp': time.time()
        }
    
    def _generate_wave_motion(self):
        """生成挥手运动"""
        # 左手左右挥动
        left_offset = 0.1 * np.sin(self.time * 3)
        left_pos = self.left_center + np.array([0.0, left_offset, 0.0])
        
        # 右手上下挥动
        right_offset = 0.1 * np.sin(self.time * 3)
        right_pos = self.right_center + np.array([0.0, 0.0, right_offset])
        
        return {
            'left_hand': {
                'position': left_pos.tolist(),
                'rotation': [1.0, 0.0, 0.0, 0.0],
                'pinch_strength': 0.0,
                'is_tracking': True
            },
            'right_hand': {
                'position': right_pos.tolist(),
                'rotation': [1.0, 0.0, 0.0, 0.0],
                'pinch_strength': 0.0,
                'is_tracking': True
            },
            'timestamp': time.time()
        }
    
    def _generate_grab_motion(self):
        """生成抓取运动(向物体移动并捏合)"""
        # 目标物体位置。这里使用与 advanced 场景中 cube 对齐的反变换坐标，
        # 这样抓取模式可以真正进入 grasp_distance 范围。
        target_pos = np.array([0.0, 0.0, -0.1])
        
        # 左手慢慢移向目标
        t = (np.sin(self.time * 0.5) + 1) / 2  # 0到1的往复
        left_pos = self.left_center + (target_pos - self.left_center) * t
        
        # 当靠近目标时增加捏合强度
        distance = np.linalg.norm(left_pos - target_pos)
        left_pinch = max(0.0, 1.0 - distance / 0.2)
        
        # 右手保持静止
        right_pos = self.right_center
        
        return {
            'left_hand': {
                'position': left_pos.tolist(),
                'rotation': [1.0, 0.0, 0.0, 0.0],
                'pinch_strength': float(left_pinch),
                'is_tracking': True
            },
            'right_hand': {
                'position': right_pos.tolist(),
                'rotation': [1.0, 0.0, 0.0, 0.0],
                'pinch_strength': 0.0,
                'is_tracking': True
            },
            'timestamp': time.time()
        }
    
    def _generate_static_data(self):
        """生成静态数据"""
        return {
            'left_hand': {
                'position': self.left_center.tolist(),
                'rotation': [1.0, 0.0, 0.0, 0.0],
                'pinch_strength': 0.0,
                'is_tracking': True
            },
            'right_hand': {
                'position': self.right_center.tolist(),
                'rotation': [1.0, 0.0, 0.0, 0.0],
                'pinch_strength': 0.0,
                'is_tracking': True
            },
            'timestamp': time.time()
        }
    
    def send_data(self, data):
        """发送数据到Isaac Lab"""
        try:
            json_data = json.dumps(data).encode('utf-8')
            self.socket.sendto(json_data, (self.host, self.port))
            return True
        except Exception as e:
            print(f"发送数据失败: {e}")
            return False
    
    def run(self, duration=None):
        """运行模拟器"""
        print(f"开始发送模拟数据到 {self.host}:{self.port}")
        print(f"频率: {self.fps} Hz")
        print(f"运动模式: {self.mode}")
        print("按 Ctrl+C 停止\n")
        
        start_time = time.time()
        frame_count = 0
        
        try:
            while True:
                # 生成并发送数据
                data = self.generate_hand_data()
                success = self.send_data(data)
                
                frame_count += 1
                
                # 每秒打印一次状态
                if frame_count % self.fps == 0:
                    elapsed = time.time() - start_time
                    actual_fps = frame_count / elapsed
                    
                    left_pos = data['left_hand']['position']
                    left_pinch = data['left_hand']['pinch_strength']
                    right_pos = data['right_hand']['position']
                    right_pinch = data['right_hand']['pinch_strength']
                    
                    print(f"[{elapsed:.1f}s] FPS: {actual_fps:.1f} | "
                          f"左手: pos=({left_pos[0]:.2f},{left_pos[1]:.2f},{left_pos[2]:.2f}) "
                          f"pinch={left_pinch:.2f} | "
                          f"右手: pos=({right_pos[0]:.2f},{right_pos[1]:.2f},{right_pos[2]:.2f}) "
                          f"pinch={right_pinch:.2f}")
                
                # 检查是否达到指定时长
                if duration and (time.time() - start_time) >= duration:
                    break
                
                # 控制发送频率
                time.sleep(self.dt)
                
        except KeyboardInterrupt:
            print("\n\n模拟器已停止")
        
        finally:
            self.socket.close()
            elapsed = time.time() - start_time
            actual_fps = frame_count / elapsed if elapsed > 0 else 0
            print(f"\n统计信息:")
            print(f"运行时间: {elapsed:.2f}秒")
            print(f"发送帧数: {frame_count}")
            print(f"平均FPS: {actual_fps:.2f}")


def main():
    parser = argparse.ArgumentParser(description='Meta Quest 手部追踪模拟器')
    parser.add_argument('--host', type=str, default='127.0.0.1',
                       help='Isaac Lab服务器地址 (默认: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8888,
                       help='UDP端口 (默认: 8888)')
    parser.add_argument('--fps', type=int, default=60,
                       help='发送频率 (默认: 60)')
    parser.add_argument('--mode', type=str, default='circle',
                       choices=['circle', 'wave', 'grab', 'static'],
                       help='运动模式 (默认: circle)')
    parser.add_argument('--duration', type=float, default=None,
                       help='运行时长(秒),默认无限运行')
    
    args = parser.parse_args()
    
    # 创建模拟器
    simulator = HandTrackingSimulator(
        host=args.host,
        port=args.port,
        fps=args.fps
    )
    simulator.mode = args.mode
    
    # 运行模拟器
    simulator.run(duration=args.duration)


if __name__ == "__main__":
    main()

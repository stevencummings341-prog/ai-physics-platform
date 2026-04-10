# Meta Quest 3S × Isaac Lab 手部追踪控制系统

使用Meta Quest 3S手部追踪在Isaac Lab虚拟物理仿真环境中实时操控虚拟手和物体。

---

## 🚀 你现在最该做什么

**当前建议不要直接跳到远程主机联调。**

你现在应该按下面顺序推进：

### 第一步：在Unity里检查引用并重新构建Quest应用

重点检查：
- `HandTrackingManager` 上的 `Left Hand`、`Right Hand`、`Left Skeleton`、`Right Skeleton` 都已绑定
- `HandTrackingUI` 上的 `handTracking` 已绑定到 `HandTrackingManager`
- `MetaQuestHandTracking.cs` 上的 `verboseLogging` 保持关闭

然后重新 `Build And Run` 到 Quest。

### 第二步：先验证Quest应用能正常打开

戴上Quest，打开应用，先不要关心远程主机是否连通，先确认：
- 应用不再一直加载
- UI能正常显示
- 没有明显卡死或闪退
- 如果此时接收端还没启动，连接状态显示 `等待远程响应` 是正常的

如果仍然卡住，立刻在本地电脑执行：

```bash
adb logcat -s Unity
```

先看首个 `NullReferenceException` 或启动阶段报错。

### 第三步：应用能打开后，再做本机链路验证

如果远程主机还没接好，先在**当前这台电脑**验证 Python 接收端是否正常：

```bash
cd /mnt/data3/yuzhixuan/vr
python3 visionpro_isaaclab_advanced.py
```

然后把 Quest 应用里的 `Server Address` 改成这台电脑的局域网 IP，再测试手部数据是否能发到 Python。

如果本机 Python 接收端已经在运行，Quest UI 应该显示：
- `连接: 远程已连接`
- `服务器: <当前电脑IP>:8888`

### 第四步：本机链路通过后，再接远程主机

确认本机验证通过后，再进入远程部署：

```bash
ssh your_username@10.20.5.3
cd /mnt/data3/yuzhixuan/vr
python3 visionpro_isaaclab_advanced.py
```

**详细步骤见下方完整文档** ⬇️

---

## 项目简介

本项目实现了Meta Quest 3S与Isaac Lab之间的实时手部追踪和物理交互，允许你用真实的手来控制虚拟环境中的对象。

**系统架构**（远程开发）：
```
Meta Quest 3S (手部追踪)
        ↓ UDP + JSON (60 Hz) via 局域网WiFi
远程电脑 Isaac Lab (Python)
        ↓ 物理仿真
虚拟手 + 物体交互

说明：Quest通过局域网WiFi直接发送数据到运行Isaac Lab的远程电脑
本地电脑仅用于Unity开发和构建Quest应用
```

**关键特性**：
- 实时手部位置和旋转追踪
- 手指捏合手势识别（抓取/释放）
- 物体拾取和操纵
- 低延迟局域网通信（<50ms）
- 完整的物理仿真（重力、碰撞、接触力）

---

## 准备清单

### 硬件要求
- **Meta Quest 3S头显**（手部追踪设备）
- **本地开发电脑**（用于Unity开发和构建Quest应用）
  - Windows/Mac/Linux均可
  - USB-C数据线（用于构建应用到Quest）
- **远程服务器/工作站**（运行Isaac Lab，IP: 10.20.5.3）
  - Linux系统（推荐Ubuntu 20.04/22.04）
  - NVIDIA GPU（推荐RTX系列，用于Isaac Sim渲染）
  - 16GB+ RAM
- **局域网连接**
  - Quest和远程电脑必须在同一局域网内
  - 推荐使用5GHz WiFi（低延迟）

### 软件要求

**本地开发电脑**：
- Unity 2022.3 LTS 或更高版本
- Meta XR All-in-One SDK
- Android SDK & NDK Tools

**远程电脑（10.20.5.3）**：
- Isaac Lab / Isaac Sim 4.0+
- Python 3.10+
- NVIDIA驱动和CUDA（用于GPU加速）

### 网络要求
- **Quest和远程电脑必须在同一局域网**（例如：都连接到同一个WiFi路由器）
- 远程电脑防火墙允许UDP 8888端口
- 本地电脑能SSH连接到远程电脑（用于启动Isaac Lab）
- 互联网连接（仅首次下载SDK时需要）

---

## 快速开始（35分钟）

**说明**：本指南针对远程开发场景 - Quest在局域网中通过WiFi连接到运行Isaac Lab的远程电脑（10.20.5.3）

---

## 📍 快速定位：我现在在哪一步？

**检查你的当前状态**：

- ✅ **Quest应用已构建好** → 直接跳到 [步骤5](#步骤5-配置远程电脑并启动isaac-lab5分钟)：SSH到远程电脑启动Isaac Lab
- ⬜ **还没有Unity项目** → 从 [步骤2](#步骤2-unity环境配置10分钟) 开始
- ⬜ **Unity项目已创建但没构建** → 跳到 [步骤4](#步骤4-构建到quest5分钟)
- ⬜ **Quest还没配置** → 从 [步骤1](#步骤1-配置meta-quest-3s5分钟) 开始

---

### 步骤1: 配置Meta Quest 3S（5分钟）

**重要**：确保Quest连接到与远程电脑（10.20.5.3）相同的WiFi网络。

#### 1.0 连接到局域网WiFi
```
Quest: 设置 > WiFi
1. 选择与远程电脑相同的WiFi网络
2. 确保连接成功（推荐5GHz频段）
3. 记下Quest的IP地址（设置 > WiFi > 当前网络 > 高级）
```

#### 1.1 启用开发者模式
```
方法1: 手机App
1. 安装Meta Quest App
2. 登录Meta账号
3. 菜单 > 设备 > 选择你的Quest
4. 开发者模式 > 开启

方法2: Quest直接设置
1. 设置 > 系统 > 开发者
2. 开启"开发者模式"
```

#### 1.2 启用USB调试
```
Quest: 设置 > 系统 > 开发者
开启: "USB调试"
开启: "USB调试(通过WiFi)"
```

#### 1.3 启用手部追踪
```
Quest: 设置 > 动作与控制器
进入: "手和控制器"
开启: "手部追踪"
设置: "自动切换"（推荐）
```

**验证**：在Quest主界面伸出手，应该能看到虚拟手显示。

---

### 步骤2: Unity环境配置（10分钟）

**在本地开发电脑上执行以下步骤**

#### 2.1 安装Unity
1. 下载Unity Hub: https://unity.com/download
2. 安装Unity 2022.3 LTS
3. 添加模块：
   - Android Build Support
   - Android SDK & NDK Tools

#### 2.2 创建项目
```
Unity Hub:
1. 新建项目
2. 模板: 3D (URP)
3. 项目名: MetaQuestHandTracking
4. 创建项目
```

#### 2.3 安装Meta XR SDK

**方法1: Package Manager（推荐）**
```
Unity编辑器:
1. Window > Package Manager
2. 点击"+"按钮
3. 选择"Add package from git URL"
4. 输入: com.meta.xr.sdk.core
5. 点击"Add"并等待安装完成
```

**方法2: Asset Store**
```
1. Window > Asset Store
2. 搜索"Meta XR All-in-One SDK"
3. 下载并导入
```

#### 2.4 项目设置

**XR设置**：
```
Edit > Project Settings > XR Plug-in Management
切换到Android标签（手机图标）
勾选: ✓ Oculus
```

**Oculus设置**：
```
Edit > Project Settings > Oculus
勾选: ✓ Hand Tracking Support
设置: Hand Tracking Frequency: High
设置: Hand Tracking Version: V2.0
```

**Android设置**：
```
Edit > Project Settings > Player > Android标签
展开Other Settings:
- Minimum API Level: Android 10.0 (API 29)
- Target API Level: Android 12.0 (API 31)
- Package Name: com.yourname.questhand
```

**验证**：
- XR Plug-in Management显示Oculus已勾选
- Oculus设置显示手部追踪已启用
- Console无错误

---

### 步骤3: 创建场景（5分钟）

#### 3.1 添加OVR Camera Rig
```
1. 删除默认的"Main Camera"
2. GameObject > XR > OVR Camera Rig
```

#### 3.2 配置手部追踪

**左手**：
```
1. 展开: OVRCameraRig > TrackingSpace > LeftHandAnchor
2. 选中LeftHandAnchor
3. Add Component > OVR Hand
   - 设置Hand Type: Hand Left
4. Add Component > OVR Skeleton
   - 设置Skeleton Type: Hand Left
```

**右手**：使用相同步骤，选择Hand Right和Skeleton Type: Hand Right

#### 3.3 添加脚本
```
1. 创建空GameObject: GameObject > Create Empty
2. 重命名为: HandTrackingManager
3. Add Component > 搜索并添加脚本
   或将[MetaQuestHandTracking.cs](MetaQuestHandTracking.cs)拖入
```

#### 3.4 连接引用

选中HandTrackingManager，在Inspector中配置：

```
Network Settings:
- Server Address: 10.20.5.3  （远程电脑的IP地址）
- Server Port: 8888
- Send Rate: 60

Hand Tracking:
- Left Hand: 拖入LeftHandAnchor下的OVRHand组件
- Right Hand: 拖入RightHandAnchor下的OVRHand组件
- Left Skeleton: 拖入LeftHandAnchor下的OVRSkeleton组件
- Right Skeleton: 拖入RightHandAnchor下的OVRSkeleton组件
```

**关键**：Server Address必须填写运行Isaac Lab的远程电脑IP：**10.20.5.3**

**如何确认远程电脑IP**：
```bash
# 在远程电脑上执行（通过SSH）
ip addr show
# 或
hostname -I

# 查找局域网IP，通常是 10.x.x.x 或 192.168.x.x
# 在本例中是：10.20.5.3
```

**验证**：
- 所有引用都已连接（Inspector中无"None"）
- Console无错误
- 场景已保存

**如果应用在Quest中一直加载、无响应**：
- 首先检查 `HandTrackingManager` 上的 `Left Hand`、`Right Hand`、`Left Skeleton`、`Right Skeleton` 是否都已绑定
- 检查 `HandTrackingUI` 脚本上的 `handTracking` 引用是否已绑定到 `HandTrackingManager`
- 确认 `MetaQuestHandTracking.cs` 的 `verboseLogging` 保持关闭，避免Quest真机被高频日志拖慢
- 用 `adb logcat -s Unity` 查看是否有 `NullReferenceException`

---

### 步骤4: 构建到Quest（5分钟）

**在本地开发电脑上执行**

#### 4.1 连接Quest
```
1. USB-C线连接Quest到电脑
2. 戴上Quest
3. 看到提示"允许USB调试" - 点击"允许"
4. 勾选"始终允许"
```

#### 4.2 验证连接

```bash
# Windows/Mac/Linux
adb devices

# 应该看到类似输出:
# List of devices attached
# 1WMHH81234567  device
```

如果看不到设备：
- 确认USB调试已启用
- 在Quest上重新授权USB调试
- 重启Quest或电脑

#### 4.3 构建
```
Unity:
1. File > Build Settings
2. 平台切换到Android（如果还没有）
   点击"Switch Platform"
3. 点击"Add Open Scenes"
4. 点击"Build And Run"
5. 选择保存位置
6. 等待构建和安装
```

**首次构建需要5-10分钟，后续会快很多。**

**验证**：
- Quest自动启动你的应用
- 能看到UI界面
- 伸出手能看到虚拟手（如果启用了OVRMesh）

---

## ✅ 如果你已完成步骤1-4（Quest应用已构建）

**恭喜！** Quest应用已经准备好了。接下来最关键的步骤：

### 🎯 接下来你需要做什么（必须按顺序）：

1. **在本地电脑打开终端** → SSH连接到远程电脑（10.20.5.3）
2. **在远程电脑上启动Isaac Lab** → 让它监听Quest的手部追踪数据
3. **在Quest上运行应用** → 连接到远程Isaac Lab

详细步骤见下方 ⬇️

---

### 步骤5: 配置远程电脑并启动Isaac Lab（5分钟）

**⚠️ 重要**：这一步必须在本地电脑的终端执行，通过SSH连接到远程电脑。

**在本地开发电脑上通过SSH连接到远程电脑执行**

#### 5.1 SSH连接到远程电脑

```bash
# 从本地电脑SSH连接到远程电脑
ssh your_username@10.20.5.3

# 如果首次连接，输入密码后会保存指纹
# 成功连接后，你将看到远程电脑的终端提示符
```

#### 5.2 配置防火墙（首次运行时必需）

```bash
# 在远程电脑上检查防火墙状态
sudo ufw status

# 如果防火墙启用，允许UDP 8888端口
sudo ufw allow 8888/udp

# 或临时关闭防火墙测试（不推荐用于生产环境）
sudo ufw disable
```

#### 5.3 进入项目目录

```bash
# 进入Isaac Lab项目目录
cd /mnt/data3/yuzhixuan/VR\ guide/
# 或你的实际路径

# 激活Isaac Sim环境（如果需要）
# 注意：根据你的Isaac Lab安装方式，可能需要激活conda环境
# source ~/IsaacLab/_isaac_sim/setup_conda_env.sh
```

#### 5.4 运行程序

```bash
# 运行高级版（推荐）
python3 visionpro_isaaclab_advanced.py

# 或基础版
# python3 visionpro_isaaclab_hand.py
```

看到以下输出表示Isaac Lab成功启动：
```
================================================================================
Isaac Lab Virtual Hand Control - Advanced
================================================================================

配置:
  服务器: 0.0.0.0:8888
  抓取阈值: 0.6
  平滑滤波: 启用

正在等待 Meta Quest 连接...
================================================================================

✓ Meta Quest receiver started on 0.0.0.0:8888
```

**注意**：保持SSH终端打开，让Isaac Lab持续运行。

**✅ 步骤5完成检查清单**：
- [ ] SSH终端显示Isaac Lab已启动
- [ ] 看到输出：`✓ Meta Quest receiver started on 0.0.0.0:8888`
- [ ] SSH终端保持打开状态（不要关闭）

**🎯 下一步**：在Quest上运行你的应用 → 见步骤6

---

### 步骤6: 连接并开始使用！

**前置条件**：
- ✅ Quest应用已构建（步骤4完成）
- ✅ 远程电脑Isaac Lab正在运行（步骤5完成，SSH终端保持打开）
- ✅ Quest和远程电脑在同一WiFi网络

**操作步骤**：

**操作步骤**：

```
1. 戴上Quest头显
2. 在应用库中找到你的应用（通常在"未知来源"分类）
3. 启动应用
4. 查看应用UI - 应该显示：
   - "连接: 远程已连接"
   - "服务器: 10.20.5.3:8888"
   - 左手和右手状态："✓"（如果追踪正常）
5. 在远程电脑的SSH终端查看 - 应该看到类似：
   [Frame 100] L:✓ R:✓ | Packets: 6000
6. 在Quest中移动你的手 → Isaac Lab窗口中的虚拟手应该跟随移动
```

**验证连接成功的标志**：
- Quest应用UI显示"连接: 远程已连接"和"服务器: 10.20.5.3:8888"
- 远程电脑SSH终端输出类似：`[Frame 100] L:✓ R:✓ | Packets: 6000`

**尝试抓取**：
```
1. 移动手靠近红色方块
2. 拇指和食指捏合
3. 移动手
4. 松开捏合释放
```

🎉 **恭喜！你已经完成设置！**

---

## 验证成功

### 检查清单
- [ ] Quest应用正常运行
- [ ] UI显示"远程已连接"
- [ ] 左右手都显示"✓"
- [ ] Isaac Lab终端显示追踪状态
- [ ] 虚拟手跟随真实手移动
- [ ] 能抓取和移动物体
- [ ] 延迟<100ms（感觉流畅）

### 性能指标

| 指标 | 目标值 | 检查方法 |
|------|--------|---------|
| 延迟 | <50ms | 观察虚拟手是否紧跟实际手 |
| 帧率 | 60 FPS | Quest Settings > 显示帧率 |
| 连接 | 稳定 | 虚拟手不应该闪烁或卡顿 |

如果全部达标 - 你成功了！🎊

---

## 常见问题

### Q1: Quest和远程电脑无法连接

**症状**：Quest应用显示"连接失败"或Isaac Lab一直显示"等待连接"

**排查步骤**：
```bash
□ Quest和远程电脑在同一WiFi网络？
□ Unity中serverAddress设置为10.20.5.3？
□ 远程电脑上Isaac Lab正在运行？（检查SSH终端）
□ 远程电脑防火墙允许8888端口？

快速测试连接：
# 在远程电脑上检查8888端口是否监听
ssh your_username@10.20.5.3
ss -tulpn | grep 8888
# 应该看到: udp   UNCONN   0   0   0.0.0.0:8888

# 从本地电脑测试UDP连接
nc -u 10.20.5.3 8888

# 测试Quest能否ping通远程电脑（在本地电脑上）
adb shell ping -c 3 10.20.5.3
```

**解决方案**：
1. 确认Quest和远程电脑在同一局域网（可以互相ping通）
2. 在远程电脑上临时关闭防火墙测试：`sudo ufw disable`
3. 确认Unity中的Server Address是**10.20.5.3**（不是localhost或127.0.0.1）
4. 重启Quest应用
5. 确认远程电脑上Isaac Lab正在运行且没有报错

---

### Q2: 手部不追踪

**症状**：UI显示"✗"或虚拟手不跟随

**排查步骤**：
```
□ Quest设置中启用了手部追踪？
□ 环境光线充足？
□ 手在Quest视野内？
□ OVRHand和OVRSkeleton正确配置？
```

**解决方案**：
1. Quest: 设置 > 手部追踪 > 重新校准
2. 确保光线充足（自然光最佳）
3. 将手保持在Quest前方30度视野内
4. 重启Quest应用

---

### Q3: 应用崩溃或无法启动

**症状**：构建成功但Quest上打开应用闪退

**排查步骤**：
```bash
□ Meta XR SDK版本正确？
□ Android API Level >= 29？
□ Unity Build时无错误？
□ Quest有足够存储空间？

查看日志：
adb logcat -s Unity
# 或
adb logcat | grep "HandTracking"
```

**解决方案**：
1. 检查Console是否有Build错误
2. 清理并重新构建（Clean > Rebuild）
3. 检查Player Settings中的API Level
4. 尝试重启Quest

---

### Q4: 物体无法被抓取

**症状**：捏合手势无效或物体不跟随手移动

**原因和解决**：

**原因1：捏合阈值太高**
```ini
# 编辑 config.ini
[grasping]
pinch_threshold = 0.5  # 降低从0.6到0.5
```

**原因2：抓取距离太小**
```ini
# 编辑 config.ini
[grasping]
grasp_distance = 0.2  # 增加从0.15到0.2
```

**原因3：手部未追踪**
- 确认Isaac Lab显示手部追踪状态

---

### Q5: 网络延迟或卡顿

**症状**：虚拟手滞后或卡顿

**优化建议**：

1. **确保Quest和远程电脑使用5GHz WiFi**
```
Quest: 设置 > WiFi > 选择5GHz网络
远程电脑: 如果使用WiFi，也切换到5GHz频段
（2.4GHz速度较慢但范围更大，5GHz速度快但范围小）
```

2. **测试网络延迟**
```bash
# 从本地电脑测试到远程电脑的延迟
ping 10.20.5.3

# 从Quest测试到远程电脑的延迟
adb shell ping -c 10 10.20.5.3

# 目标：延迟应该 < 10ms
```

3. **降低发送频率**（如果延迟仍然高）
```csharp
// MetaQuestHandTracking.cs
public int sendRate = 30;  // 从60降到30
```

4. **检查远程电脑CPU/GPU使用率**
```bash
# SSH到远程电脑
ssh your_username@10.20.5.3

# 查看资源使用
htop  # 或 top

# 如果CPU/GPU使用率>80%，考虑：
# - 降低Isaac Lab画质
# - 关闭其他占用资源的程序
```

5. **网络优化**
- 确保Quest和远程电脑距离WiFi路由器较近
- 避免障碍物遮挡
- 考虑为远程电脑使用有线网络连接（网线连接到路由器）

---

## 使用技巧

### 获得最佳追踪效果
1. **光照**：确保房间光线充足（自然光最佳）
2. **手的位置**：保持手在Quest前方视野内
3. **手势清晰**：捏合时拇指和食指接触明显
4. **网络稳定**：使用5GHz WiFi或有线连接

### 常用手势
```
✋ 张开手 = 未抓取
🤏 捏合 (> 0.6) = 抓取
👐 松开 = 释放
```

### 调试技巧

**查看Quest日志**：
```bash
# 在本地电脑上
adb logcat -s Unity
# 或过滤特定标签
adb logcat | grep "HandTracking"
```

**查看远程电脑Isaac Lab日志**：
```bash
# SSH到远程电脑
ssh your_username@10.20.5.3

# 查看Python程序输出（如果在后台运行）
# 或直接在运行Isaac Lab的SSH终端查看实时输出
```

**测试网络连接**：
```bash
# 测试Quest能否ping通远程电脑
adb shell ping -c 5 10.20.5.3

# 测试UDP端口连接（在本地电脑上）
nc -u 10.20.5.3 8888
# 输入任意文字，按回车
# 查看远程电脑SSH终端是否收到数据
```

**测试模式（无Quest）**：
```bash
# 在本地电脑上模拟Quest发送数据
python3 test_hand_tracking.py --mode circle --host 10.20.5.3

# 在远程电脑上运行Isaac Lab
ssh your_username@10.20.5.3
cd /mnt/data3/yuzhixuan/vr
python3 visionpro_isaaclab_advanced.py
```

---

## 下一步学习

### 深入了解
- **[TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md)** - 完整技术参考手册
  - 系统架构详解
  - 通信协议规范
  - 坐标系转换
  - config.ini完整参数说明
  - 性能优化策略
  - 扩展开发指南

### 定制修改

**调整抓取灵敏度**：
```ini
# 编辑 config.ini
[grasping]
pinch_threshold = 0.5  # 降低使抓取更容易
grasp_distance = 0.2   # 增加抓取范围
```

**调整发送频率**：
```csharp
// 编辑 MetaQuestHandTracking.cs
public int sendRate = 30;  # 降低减少网络负载
```

**添加新物体**：
```python
# 编辑 visionpro_isaaclab_advanced.py
# 在VirtualHandSceneCfg中添加新对象配置
# 参考现有的cube、sphere、cylinder配置
```

详细说明请参考[TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md)的"扩展开发"章节。

---

## 核心代码文件

### Python代码
- [visionpro_isaaclab_advanced.py](visionpro_isaaclab_advanced.py) - 高级版（推荐）
- [visionpro_isaaclab_hand.py](visionpro_isaaclab_hand.py) - 基础版
- [test_hand_tracking.py](test_hand_tracking.py) - 测试模拟器

### Unity C#代码
- [MetaQuestHandTracking.cs](MetaQuestHandTracking.cs) - Quest手部追踪主脚本
- [HandTrackingUI.cs](HandTrackingUI.cs) - UI控制脚本

### 配置文件
- [config.ini](config.ini) - 所有参数配置
- requirements.txt - Python依赖
- start.sh - 启动脚本

---

## 快速命令参考

```bash
# ========== 本地开发电脑 ==========
# 检查Quest连接
adb devices

# 查看Quest日志
adb logcat -s Unity

# 测试Quest能否连接远程电脑
adb shell ping -c 3 10.20.5.3

# 运行测试模拟器（发送数据到远程电脑）
python3 test_hand_tracking.py --mode circle --host 10.20.5.3

# ========== 远程电脑（SSH连接） ==========
# SSH连接到远程电脑
ssh your_username@10.20.5.3

# 进入项目目录
cd /mnt/data3/yuzhixuan/vr

# 配置防火墙（首次运行）
sudo ufw allow 8888/udp

# 启动Isaac Lab
python3 visionpro_isaaclab_advanced.py

# 检查8888端口监听状态
ss -tulpn | grep 8888

# 查看网络包统计
sudo tcpdump -i any udp port 8888 -c 10

# 查看远程电脑IP
hostname -I
```

---

## 故障排查快速决策树

```
无法连接？
├─ 远程电脑上Isaac Lab在运行？ → NO → SSH连接并启动
├─ Quest和远程电脑在同一WiFi？ → NO → 连接到同一网络
├─ Unity中IP是10.20.5.3？ → NO → 更新Unity中的serverAddress
├─ 远程电脑防火墙允许8888？ → NO → sudo ufw allow 8888/udp
└─ 测试网络连通性 → adb shell ping 10.20.5.3

手部不追踪？
├─ Quest设置已启用？ → NO → 启用手部追踪
├─ 光线充足？ → NO → 增加照明
├─ 手在视野内？ → NO → 调整手的位置
└─ OVRHand配置正确？ → NO → 检查Unity配置

无法抓取物体？
├─ 手部正在追踪？ → NO → 解决追踪问题
├─ 距离够近？(<15cm) → NO → 靠近物体
├─ 捏合力度够大？(>0.6) → NO → 用力捏合
└─ 还是不行？ → 降低config.ini中的阈值

应用崩溃？
├─ Build有错误？ → YES → 修复错误
├─ API Level正确？ → NO → 设置为API 29+
├─ Meta XR SDK已安装？ → NO → 安装SDK
└─ 查看adb logcat日志
```

---

## 专业提示

1. **首次设置慢是正常的** - Unity首次构建需要时间
2. **保存场景为Prefab** - 方便复用配置
3. **使用版本控制** - 推荐Git管理项目
4. **测试先行** - 使用[test_hand_tracking.py](test_hand_tracking.py)模拟器先测试
5. **阅读技术文档** - 深入了解请看[TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md)

---

## 系统要求

### 本地开发电脑（用于Unity开发）
**最低要求**：
- Unity 2022.3 LTS
- 8GB RAM
- Windows 10/Mac OS 12/Ubuntu 20.04

**推荐配置**：
- Unity 2023.2+
- 16GB+ RAM
- SSD存储

### 远程电脑（运行Isaac Lab，IP: 10.20.5.3）
**最低要求**：
- Meta Quest 3S
- Python 3.10+
- NVIDIA GPU（支持CUDA）
- 16GB RAM
- Ubuntu 20.04/22.04

**推荐配置**：
- NVIDIA RTX 3060或更高
- 32GB+ RAM
- SSD存储
- 有线网络连接（连接到路由器）

### 网络要求
- Quest和远程电脑在同一局域网
- 5GHz WiFi（推荐）
- 网络延迟 < 10ms

---

**版本**: 1.1（远程开发版）
**更新**: 2025-01
**兼容**: Meta Quest 3S, Unity 2022.3+, Isaac Lab 4.0+
**场景**: Quest通过局域网WiFi连接到远程电脑（10.20.5.3）运行的Isaac Lab

**需要帮助？** 查看[TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md)或检查上述常见问题。

**祝你成功！** 🚀🤖✋

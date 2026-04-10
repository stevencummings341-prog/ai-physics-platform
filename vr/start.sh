#!/bin/bash

# Isaac Lab虚拟手控制系统 - 快速启动脚本

PYTHON_BIN="${PYTHON_BIN:-python3}"
ISAAC_ENV_SCRIPT="${ISAAC_ENV_SCRIPT:-$HOME/IsaacLab/_isaac_sim/setup_conda_env.sh}"

echo "====================================="
echo "Isaac Lab虚拟手控制系统"
echo "====================================="
echo ""

# 尝试激活Isaac Sim环境
if [ -f "$ISAAC_ENV_SCRIPT" ]; then
    echo "检测到Isaac环境脚本，正在激活: $ISAAC_ENV_SCRIPT"
    # shellcheck disable=SC1090
    source "$ISAAC_ENV_SCRIPT"
fi

# 检查当前Python是否真的可用
if ! "$PYTHON_BIN" -c "import omni.isaac.lab" >/dev/null 2>&1; then
    echo "❌ 错误: 当前Python环境无法导入 omni.isaac.lab"
    echo "请确认以下其中一项："
    echo "  1. 已安装Isaac Lab / Isaac Sim"
    echo "  2. 已激活正确的conda环境"
    echo "  3. ISAAC_ENV_SCRIPT 指向正确的 setup_conda_env.sh"
    exit 1
fi

# 获取本机IP地址
echo "正在获取本机IP地址..."
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    IP=$(hostname -I | awk '{print $1}')
elif [[ "$OSTYPE" == "darwin"* ]]; then
    IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
else
    echo "⚠️  无法自动检测IP地址,请手动查看"
    IP="未知"
fi

echo ""
echo "本机IP地址: $IP"
echo "UDP端口: 8888"
echo ""

# 选择启动模式
echo "请选择启动模式:"
echo "1) 真实模式 (使用 Meta Quest)"
echo "2) 测试模式 (使用模拟器)"
echo ""
read -p "请输入选项 (1/2): " mode

if [ "$mode" == "1" ]; then
    echo ""
    echo "====================================="
    echo "真实模式"
    echo "====================================="
    echo ""
    echo "步骤:"
    echo "1. 在 Meta Quest 上打开手部追踪应用"
    echo "2. 输入服务器地址: $IP"
    echo "3. 输入端口: 8888"
    echo "4. 点击'开始追踪'"
    echo ""
    echo "正在启动Isaac Lab..."
    echo ""
    
    "$PYTHON_BIN" visionpro_isaaclab_advanced.py
    
elif [ "$mode" == "2" ]; then
    echo ""
    echo "====================================="
    echo "测试模式"
    echo "====================================="
    echo ""
    echo "请选择运动模式:"
    echo "1) circle - 圆周运动"
    echo "2) wave - 挥手运动"
    echo "3) grab - 抓取运动"
    echo "4) static - 静止"
    echo ""
    read -p "请输入选项 (1-4): " motion_mode
    
    case $motion_mode in
        1) motion="circle" ;;
        2) motion="wave" ;;
        3) motion="grab" ;;
        4) motion="static" ;;
        *) motion="circle" ;;
    esac
    
    echo ""
    echo "正在启动测试环境..."
    echo ""
    
    # 在后台启动Isaac Lab
    "$PYTHON_BIN" visionpro_isaaclab_advanced.py &
    ISAAC_PID=$!
    
    # 等待Isaac Lab启动
    echo "等待Isaac Lab启动 (3秒)..."
    sleep 3
    
    # 启动模拟器
    echo "启动手部追踪模拟器..."
    "$PYTHON_BIN" test_hand_tracking.py --mode "$motion" --fps 60
    
    # 清理
    kill $ISAAC_PID 2>/dev/null
    
else
    echo "无效的选项"
    exit 1
fi

echo ""
echo "程序已退出"

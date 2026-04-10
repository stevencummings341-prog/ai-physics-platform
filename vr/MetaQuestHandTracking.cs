/*
 * Meta Quest 3S Hand Tracking Sender
 * 在Meta Quest 3S上运行，捕获手部追踪数据并发送到Isaac Lab
 * 
 * 需要: Unity + Meta XR SDK
 */

using UnityEngine;
using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using TMPro;

public class MetaQuestHandTracking : MonoBehaviour
{
    [Header("Network Settings")]
    [Tooltip("Isaac Lab服务器的IP地址")]
    public string serverAddress = "10.20.5.3";  // 远程电脑IP地址
    
    [Tooltip("服务器端口")]
    public int serverPort = 8888;
    
    [Tooltip("发送频率 (Hz)")]
    public int sendRate = 60;
    
    [Header("Hand Tracking")]
    [Tooltip("左手追踪")]
    public OVRHand leftHand;
    
    [Tooltip("右手追踪")]
    public OVRHand rightHand;
    
    [Tooltip("左手骨骼")]
    public OVRSkeleton leftSkeleton;
    
    [Tooltip("右手骨骼")]
    public OVRSkeleton rightSkeleton;
    
    [Header("UI References")]
    public TextMeshProUGUI statusText;
    public TextMeshProUGUI leftHandStatus;
    public TextMeshProUGUI rightHandStatus;
    public GameObject leftHandIndicator;
    public GameObject rightHandIndicator;

    [Header("Diagnostics")]
    [Tooltip("启用后会输出更多调试日志。Quest真机上建议关闭。")]
    public bool verboseLogging = false;

    [Tooltip("状态日志的打印间隔帧数。")]
    public int statusLogIntervalFrames = 300;
    
    // UDP客户端
    private UdpClient udpClient;
    private IPEndPoint remoteEndPoint;
    
    // 追踪状态
    private bool isTracking = false;
    private bool isConnected = false;
    
    // 发送计时器
    private float sendTimer = 0f;
    private float sendInterval;
    
    // 统计
    private int packetsSent = 0;
    private int sendErrors = 0;
    private string lastErrorMessage = "";
    private readonly object connectionStateLock = new object();
    private Thread ackThread;
    private bool ackThreadRunning = false;
    private bool hasRecentAck = false;
    private bool hasEverReceivedAck = false;
    private double lastAckUtcSeconds = 0.0;

    private const double ServerHeartbeatTimeoutSeconds = 1.5;

    public bool IsNetworkReady
    {
        get
        {
            lock (connectionStateLock)
            {
                return isConnected && udpClient != null && remoteEndPoint != null;
            }
        }
    }

    public bool IsServerConnected
    {
        get
        {
            lock (connectionStateLock)
            {
                return hasRecentAck;
            }
        }
    }

    public string ConnectionStatusLabel
    {
        get
        {
            lock (connectionStateLock)
            {
                if (!(isConnected && udpClient != null && remoteEndPoint != null))
                {
                    return "网络错误";
                }

                if (hasRecentAck)
                {
                    return "远程已连接";
                }

                return hasEverReceivedAck ? "远程未响应" : "等待远程响应";
            }
        }
    }

    public bool IsTrackingActive => isTracking;
    public int PacketsSent => packetsSent;
    public int SendErrors => sendErrors;
    public string LastErrorMessage
    {
        get
        {
            lock (connectionStateLock)
            {
                return lastErrorMessage;
            }
        }
    }
    
    void Start()
    {
        sendRate = Mathf.Max(1, sendRate);
        sendInterval = 1f / sendRate;
        InitializeNetwork();

        if (verboseLogging)
        {
            Debug.Log("[HandTracking] ========== Script Starting ==========");
            Debug.Log($"[HandTracking] Server: {serverAddress}:{serverPort}");
            Debug.Log($"[HandTracking] Send Rate: {sendRate} Hz");
            Debug.Log($"[HandTracking] leftHand assigned: {leftHand != null}");
            Debug.Log($"[HandTracking] rightHand assigned: {rightHand != null}");
            Debug.Log($"[HandTracking] leftSkeleton assigned: {leftSkeleton != null}");
            Debug.Log($"[HandTracking] rightSkeleton assigned: {rightSkeleton != null}");
        }

        if (leftHand == null && rightHand == null)
        {
            Debug.LogWarning("[HandTracking] 左右手引用都未绑定，应用不会发送手部数据。");
        }

        UpdateStatusUI();
    }
    
    void InitializeNetwork()
    {
        CloseNetworkClient();

        lock (connectionStateLock)
        {
            lastErrorMessage = "";
            isConnected = false;
            hasRecentAck = false;
            hasEverReceivedAck = false;
            lastAckUtcSeconds = 0.0;
        }

        if (string.IsNullOrWhiteSpace(serverAddress))
        {
            SetNetworkError("服务器地址为空");
            return;
        }

        if (serverPort <= 0 || serverPort > 65535)
        {
            SetNetworkError($"端口无效: {serverPort}");
            return;
        }

        try
        {
            if (!IPAddress.TryParse(serverAddress, out IPAddress parsedAddress))
            {
                SetNetworkError($"IP地址格式无效: {serverAddress}");
                return;
            }

            udpClient = new UdpClient();
            udpClient.Client.ReceiveTimeout = 500;
            remoteEndPoint = new IPEndPoint(parsedAddress, serverPort);

            lock (connectionStateLock)
            {
                isConnected = true;
            }

            StartAckReceiver();

            if (verboseLogging)
            {
                Debug.Log($"[HandTracking] UDP client initialized: {serverAddress}:{serverPort}");
            }
        }
        catch (Exception e)
        {
            SetNetworkError($"初始化网络失败: {e.Message}");
        }
    }
    
    void Update()
    {
        RefreshServerConnectionState();

        // 检查手部追踪状态
        bool leftTracking = leftHand != null && leftHand.IsTracked;
        bool rightTracking = rightHand != null && rightHand.IsTracked;
        
        isTracking = leftTracking || rightTracking;
        
        // 定期打印状态
        if (verboseLogging && statusLogIntervalFrames > 0 && Time.frameCount % statusLogIntervalFrames == 0)
        {
            Debug.Log($"[HandTracking] Status - Left:{leftTracking} Right:{rightTracking} Connected:{isConnected} Tracking:{isTracking}");
        }
        
        // 更新UI指示器
        if (leftHandIndicator != null)
            leftHandIndicator.SetActive(leftTracking);
        if (rightHandIndicator != null)
            rightHandIndicator.SetActive(rightTracking);
        
        // 定时发送数据
        sendTimer += Time.deltaTime;
        if (sendTimer >= sendInterval && isTracking && isConnected)
        {
            SendHandData();
            sendTimer -= sendInterval;
        }
        
        // 更新UI (每0.5秒更新一次)
        if (Time.frameCount % 30 == 0)
        {
            UpdateStatusUI();
        }
    }
    
    void SendHandData()
    {
        if (!IsNetworkReady)
        {
            return;
        }

        try
        {
            // 构建JSON数据
            HandTrackingData data = new HandTrackingData();
            
            // 左手数据
            if (leftHand != null && leftHand.IsTracked)
            {
                data.left_hand = GetHandData(leftHand, leftSkeleton);
            }
            else
            {
                data.left_hand = new HandData { is_tracking = false };
            }
            
            // 右手数据
            if (rightHand != null && rightHand.IsTracked)
            {
                data.right_hand = GetHandData(rightHand, rightSkeleton);
            }
            else
            {
                data.right_hand = new HandData { is_tracking = false };
            }
            
            data.timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;
            
            // 序列化为JSON
            string json = JsonUtility.ToJson(data);
            byte[] bytes = Encoding.UTF8.GetBytes(json);

            // 发送UDP数据包
            udpClient.Send(bytes, bytes.Length, remoteEndPoint);
            packetsSent++;

            if (verboseLogging && packetsSent % 120 == 0)
            {
                Debug.Log($"[HandTracking] Packets sent: {packetsSent}");
            }
        }
        catch (Exception e)
        {
            sendErrors++;
            SetNetworkError($"发送失败: {e.Message}");
        }
    }
    
    HandData GetHandData(OVRHand hand, OVRSkeleton skeleton)
    {
        HandData handData = new HandData();

        // 骨骼初始化经常滞后于IsTracked，空判断必须严格，否则Quest上容易在启动阶段报错。
        Transform sourceTransform = ResolveHandTransform(hand, skeleton);
        Vector3 pos = sourceTransform.position;
        Quaternion rot = sourceTransform.rotation;

        // 转换为Isaac Lab坐标系
        // Unity: Y向上, Z向前, X向右
        // Isaac Lab需要: Z向上, X向前, Y向左
        handData.position = new float[] {
            pos.z,
            -pos.x,
            pos.y
        };

        handData.rotation = new float[] {
            rot.w,
            rot.z,
            -rot.x,
            rot.y
        };
        
        // 计算捏合强度
        handData.pinch_strength = hand.GetFingerPinchStrength(OVRHand.HandFinger.Index);
        handData.is_tracking = true;
        
        return handData;
    }

    Transform ResolveHandTransform(OVRHand hand, OVRSkeleton skeleton)
    {
        if (skeleton != null && skeleton.Bones != null && skeleton.Bones.Count > 0)
        {
            foreach (OVRBone bone in skeleton.Bones)
            {
                if (bone != null && bone.Transform != null)
                {
                    return bone.Transform;
                }
            }
        }

        return hand.transform;
    }
    
    void UpdateStatusUI()
    {
        if (statusText != null)
        {
            string errorMessage = LastErrorMessage;
            string errorLine = string.IsNullOrEmpty(errorMessage) ? "" : $"\n错误: {errorMessage}";

            statusText.text = $"连接: {ConnectionStatusLabel}\n" +
                            $"服务器: {serverAddress}:{serverPort}\n" +
                            $"已发送: {packetsSent} 包\n" +
                            $"错误计数: {sendErrors}" +
                            errorLine;
        }
        
        if (leftHandStatus != null)
        {
            bool tracking = leftHand != null && leftHand.IsTracked;
            float pinch = tracking ? leftHand.GetFingerPinchStrength(OVRHand.HandFinger.Index) : 0f;
            leftHandStatus.text = $"左手: {(tracking ? "✓" : "✗")}\n捏合: {pinch:F2}";
        }
        
        if (rightHandStatus != null)
        {
            bool tracking = rightHand != null && rightHand.IsTracked;
            float pinch = tracking ? rightHand.GetFingerPinchStrength(OVRHand.HandFinger.Index) : 0f;
            rightHandStatus.text = $"右手: {(tracking ? "✓" : "✗")}\n捏合: {pinch:F2}";
        }
    }
    
    public void SetServerAddress(string address)
    {
        serverAddress = address;
        InitializeNetwork();
        UpdateStatusUI();
    }
    
    public void SetServerPort(int port)
    {
        serverPort = port;
        InitializeNetwork();
        UpdateStatusUI();
    }
    
    void OnDestroy()
    {
        CloseNetworkClient();
    }
    
    void OnApplicationQuit()
    {
        CloseNetworkClient();
    }

    void CloseNetworkClient()
    {
        ackThreadRunning = false;

        if (udpClient != null)
        {
            udpClient.Close();
            udpClient = null;
        }

        if (ackThread != null && ackThread.IsAlive && Thread.CurrentThread != ackThread)
        {
            ackThread.Join(300);
        }

        ackThread = null;
        remoteEndPoint = null;

        lock (connectionStateLock)
        {
            isConnected = false;
            hasRecentAck = false;
        }
    }

    void SetNetworkError(string message)
    {
        lock (connectionStateLock)
        {
            lastErrorMessage = message;
            isConnected = false;
            hasRecentAck = false;
        }

        Debug.LogError($"[HandTracking] {message}");
    }

    void StartAckReceiver()
    {
        ackThreadRunning = true;
        ackThread = new Thread(AckReceiveLoop);
        ackThread.IsBackground = true;
        ackThread.Start();
    }

    void AckReceiveLoop()
    {
        IPEndPoint anyEndpoint = new IPEndPoint(IPAddress.Any, 0);

        while (ackThreadRunning)
        {
            try
            {
                if (udpClient == null)
                {
                    break;
                }

                byte[] bytes = udpClient.Receive(ref anyEndpoint);
                string payload = Encoding.UTF8.GetString(bytes);
                AckMessage ack = JsonUtility.FromJson<AckMessage>(payload);

                if (ack != null && ack.type == "ack")
                {
                    lock (connectionStateLock)
                    {
                        hasRecentAck = true;
                        hasEverReceivedAck = true;
                        lastAckUtcSeconds = GetCurrentUtcSeconds();
                    }
                }
            }
            catch (SocketException socketException)
            {
                if (socketException.SocketErrorCode == SocketError.TimedOut)
                {
                    continue;
                }

                if (!ackThreadRunning || udpClient == null)
                {
                    break;
                }

                if (verboseLogging)
                {
                    Debug.LogWarning($"[HandTracking] 接收ACK异常: {socketException.Message}");
                }
            }
            catch (ObjectDisposedException)
            {
                break;
            }
            catch (Exception e)
            {
                if (ackThreadRunning && verboseLogging)
                {
                    Debug.LogWarning($"[HandTracking] 解析ACK失败: {e.Message}");
                }
            }
        }
    }

    void RefreshServerConnectionState()
    {
        lock (connectionStateLock)
        {
            if (hasRecentAck && (GetCurrentUtcSeconds() - lastAckUtcSeconds) > ServerHeartbeatTimeoutSeconds)
            {
                hasRecentAck = false;
            }
        }
    }

    double GetCurrentUtcSeconds()
    {
        return DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;
    }
}

// 数据结构
[System.Serializable]
public class HandTrackingData
{
    public HandData left_hand;
    public HandData right_hand;
    public double timestamp;
}

[System.Serializable]
public class AckMessage
{
    public string type;
    public string server_status;
    public double server_time;
    public int packets_received;
}

[System.Serializable]
public class HandData
{
    public float[] position = new float[3];
    public float[] rotation = new float[4];
    public float pinch_strength;
    public bool is_tracking;
}

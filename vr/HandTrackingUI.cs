/*
 * Meta Quest Hand Tracking UI Controller
 * UI界面控制和输入处理
 */

using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class HandTrackingUI : MonoBehaviour
{
    [Header("References")]
    public MetaQuestHandTracking handTracking;
    
    [Header("Input Fields")]
    public TMP_InputField serverAddressInput;
    public TMP_InputField serverPortInput;
    
    [Header("Status Displays")]
    public TextMeshProUGUI connectionStatusText;
    public TextMeshProUGUI leftHandStatusText;
    public TextMeshProUGUI rightHandStatusText;
    public TextMeshProUGUI statsText;
    
    [Header("Visual Indicators")]
    public Image connectionIndicator;
    public Image leftHandIndicator;
    public Image rightHandIndicator;
    
    [Header("Colors")]
    public Color connectedColor = Color.green;
    public Color disconnectedColor = Color.red;
    public Color waitingColor = new Color(1.0f, 0.8f, 0.2f);
    public Color trackingColor = Color.blue;
    public Color notTrackingColor = Color.gray;
    
    void Start()
    {
        if (handTracking == null)
        {
            Debug.LogError("[HandTrackingUI] handTracking 脚本未绑定，UI将进入只读错误状态。");
            UpdateConnectionStatus();
            UpdateHandStatus();
            UpdateStats();
            return;
        }

        // 初始化输入框
        if (serverAddressInput != null)
        {
            serverAddressInput.text = handTracking.serverAddress;
            serverAddressInput.onEndEdit.AddListener(OnServerAddressChanged);
        }
        
        if (serverPortInput != null)
        {
            serverPortInput.text = handTracking.serverPort.ToString();
            serverPortInput.onEndEdit.AddListener(OnServerPortChanged);
        }
    }
    
    void Update()
    {
        UpdateConnectionStatus();
        UpdateHandStatus();
        UpdateStats();
    }
    
    void UpdateConnectionStatus()
    {
        bool localReady = handTracking != null && handTracking.IsNetworkReady;
        bool serverConnected = handTracking != null && handTracking.IsServerConnected;
        string statusLabel = handTracking != null ? handTracking.ConnectionStatusLabel : "脚本未绑定";

        if (connectionStatusText != null)
        {
            if (handTracking == null)
            {
                connectionStatusText.text = "脚本未绑定";
            }
            else if (!string.IsNullOrEmpty(handTracking.LastErrorMessage))
            {
                connectionStatusText.text = $"{statusLabel}\n{handTracking.LastErrorMessage}";
            }
            else
            {
                connectionStatusText.text = statusLabel;
            }
        }
        
        if (connectionIndicator != null)
        {
            if (serverConnected)
            {
                connectionIndicator.color = connectedColor;
            }
            else if (localReady)
            {
                connectionIndicator.color = waitingColor;
            }
            else
            {
                connectionIndicator.color = disconnectedColor;
            }
        }
    }
    
    void UpdateHandStatus()
    {
        if (handTracking == null)
        {
            if (leftHandStatusText != null)
                leftHandStatusText.text = "左手\n脚本未绑定";
            if (rightHandStatusText != null)
                rightHandStatusText.text = "右手\n脚本未绑定";
            if (leftHandIndicator != null)
                leftHandIndicator.color = notTrackingColor;
            if (rightHandIndicator != null)
                rightHandIndicator.color = notTrackingColor;
            return;
        }

        // 左手状态
        if (leftHandStatusText != null && handTracking.leftHand != null)
        {
            bool tracking = handTracking.leftHand.IsTracked;
            float pinch = tracking ? 
                handTracking.leftHand.GetFingerPinchStrength(OVRHand.HandFinger.Index) : 0f;
            
            leftHandStatusText.text = $"左手\n{(tracking ? "追踪中" : "未追踪")}\n" +
                                     $"捏合: {pinch:F2}";
        }
        
        if (leftHandIndicator != null && handTracking.leftHand != null)
        {
            bool tracking = handTracking.leftHand.IsTracked;
            leftHandIndicator.color = tracking ? trackingColor : notTrackingColor;
        }
        else if (leftHandStatusText != null && handTracking.leftHand == null)
        {
            leftHandStatusText.text = "左手\n未绑定";
        }
        if (leftHandIndicator != null && handTracking.leftHand == null)
        {
            leftHandIndicator.color = notTrackingColor;
        }
        
        // 右手状态
        if (rightHandStatusText != null && handTracking.rightHand != null)
        {
            bool tracking = handTracking.rightHand.IsTracked;
            float pinch = tracking ? 
                handTracking.rightHand.GetFingerPinchStrength(OVRHand.HandFinger.Index) : 0f;
            
            rightHandStatusText.text = $"右手\n{(tracking ? "追踪中" : "未追踪")}\n" +
                                      $"捏合: {pinch:F2}";
        }
        
        if (rightHandIndicator != null && handTracking.rightHand != null)
        {
            bool tracking = handTracking.rightHand.IsTracked;
            rightHandIndicator.color = tracking ? trackingColor : notTrackingColor;
        }
        else if (rightHandStatusText != null && handTracking.rightHand == null)
        {
            rightHandStatusText.text = "右手\n未绑定";
        }
        if (rightHandIndicator != null && handTracking.rightHand == null)
        {
            rightHandIndicator.color = notTrackingColor;
        }
    }
    
    void UpdateStats()
    {
        if (statsText != null)
        {
            if (handTracking == null)
            {
                statsText.text = "未找到 MetaQuestHandTracking 脚本";
                return;
            }

            float fps = Time.deltaTime > 0f ? 1f / Time.deltaTime : 0f;
            statsText.text = $"服务器: {handTracking.serverAddress}:{handTracking.serverPort}\n" +
                           $"连接状态: {handTracking.ConnectionStatusLabel}\n" +
                           $"帧率: {fps:F0} FPS\n" +
                           $"发送速率: {handTracking.sendRate} Hz\n" +
                           $"已发送: {handTracking.PacketsSent} 包";
        }
    }
    
    public void OnServerAddressChanged(string newAddress)
    {
        if (handTracking != null && !string.IsNullOrEmpty(newAddress))
        {
            handTracking.SetServerAddress(newAddress);
            Debug.Log($"Server address changed to: {newAddress}");
        }
    }
    
    public void OnServerPortChanged(string newPort)
    {
        if (handTracking != null && int.TryParse(newPort, out int port))
        {
            handTracking.SetServerPort(port);
            Debug.Log($"Server port changed to: {port}");
        }
    }
    
    // 可以从UI按钮调用的辅助方法
    public void Reconnect()
    {
        if (handTracking != null)
        {
            // 重新初始化连接
            handTracking.SetServerAddress(handTracking.serverAddress);
        }
    }
    
    public void ShowHelp()
    {
        // 显示帮助面板
        Debug.Log("显示帮助信息");
    }
    
    public void QuitApplication()
    {
        Application.Quit();
    }
}

// ui-controller.js
import { DOM } from "./dom.js";
import { TypeWriter } from "./type-writer.js";
import { EmotionController } from "../features/emotion/controller.js";
import EventBus from "../core/event-bus.js";

export class UIController {
  constructor() {
    this.emotionSystem = new EmotionController();
    this.writer = new TypeWriter(DOM.input);
    this.speed = 50;

    this.ai_name = "钦灵";
    this.ai_subtitle = "Slime Studio";
    this.user_name = "可爱的你";
    this.user_subtitle = "Bilibili";

    this.userId = 1;
    this.character_id = 1;

    // 绑定实例方法
    this.handleSend = this.handleSend.bind(this);
    this.handleKeyPress = this.handleKeyPress.bind(this);

    this.init();
  }

  init() {
    this.bindEventListeners();
    this.setupGlobalHandlers();
    this.getAndApplyAIInfo();
  }

  destroy() {
    DOM.sendBtn?.removeEventListener("click", this.handleSend);
    document?.removeEventListener("keypress", this.handleKeyPress);
  }

  // 这里是整个ui初始化的地方，务必重视
  async getAndApplyAIInfo() {
    try {
      const response = await fetch(
        `/api/v1/chat/info/init?user_id=${this.userId}`
      );
      const result = await response.json();

      if (result.code !== 200) {
        throw new Error(result.message || "读取失败");
      }

      this.ai_name = result.data.ai_name;
      this.ai_subtitle = result.data.ai_subtitle;
      this.user_name = result.data.user_name;
      this.user_subtitle = result.data.user_subtitle;
      this.character_id = result.data.character_id;

      // 动态设置 transform 和 transform-origin
      DOM.avatar.img.style.transform = `scale(${result.data.scale})`; // 调整缩放
      DOM.avatar.img.style.transformOrigin = `center ${result.data.offset}%`; // 调整放大基准点

      this.resetAvatar();

      // 发送事件，方便其他地方监听
      EventBus.emit("ui:name-updated", {
        ai_name: this.ai_name,
        ai_subtitle: this.ai_subtitle,
        user_name: this.user_name,
        user_subtitle: this.user_subtitle,
      });
    } catch (error) {
      console.log("读取失败", error);
    }
  }

  resetAvatar() {
    DOM.avatar.title.textContent = this.user_name;
    DOM.avatar.subtitle.textContent = this.user_subtitle;

    this.emotionSystem.setEmotion("正常", { force: true });
    DOM.image.kousanPreviewImg.src =
      "/api/v1/chat/character/get_avatar/正常.png";
  }

  bindEventListeners() {
    DOM.sendBtn?.addEventListener("click", this.handleSend);
    document?.addEventListener("keypress", this.handleKeyPress);
  }

  setupGlobalHandlers() {
    // 更新角色和信息事件
    EventBus.on("system:character_updated", () => {
      this.getAndApplyAIInfo();
    });

    // 接受消息事件
    EventBus.on("chat:message", (data) => {
      DOM.input.placeholder = "";

      let displayText = "";

      if (data.motionText && data.motionText !== "") {
        displayText = data.content + "（" + data.motionText + "）";
      } else {
        displayText = data.content;
      }

      // 显示消息内容
      this.writer.start(displayText, this.speed);

      // 更新情绪
      if (data.emotion) {
        this.emotionSystem.setEmotion(data.emotion);
        DOM.avatar.emotion.textContent = data.originalTag;
      }

      // 处理音频
      if (data.audioFile) {
        DOM.audioPlayer.src = `../audio/${data.audioFile}`;
        DOM.audioPlayer.load();
        DOM.audioPlayer.play();
      }
    });

    // 启用输入事件
    EventBus.on("chat:input-enabled", () => {
      DOM.input.placeholder = "输入消息...";
      DOM.input.disabled = false;
      DOM.input.value = "";
      DOM.avatar.title.textContent = this.user_name;
      DOM.avatar.subtitle.textContent = this.user_subtitle;
      DOM.avatar.emotion.textContent = "";
      this.writer.stop();
    });

    // 等待AI回复事件
    EventBus.on("chat:thinking", (isThinking) => {
      if (isThinking) {
        DOM.input.disabled = true;
        DOM.input.value = "";
        this.emotionSystem.setEmotion("AI思考");
        DOM.input.placeholder = "灵灵正在思考...";
        DOM.avatar.title.textContent = this.ai_name;
        DOM.avatar.subtitle.textContent = this.ai_subtitle;
        DOM.avatar.emotion.textContent = "";
      } else {
        DOM.input.disabled = false;
      }
    });

    // 监听 WebSocket 状态更新
    EventBus.on("connection:open", () => {
      if (DOM.status) DOM.status.textContent = "✅ 已连接服务器";
      if (DOM.sendBtn) DOM.sendBtn.disabled = false;
    });

    EventBus.on("connection:dead", () => {
      if (DOM.status) DOM.status.textContent = "❌ 无法连接服务器";
      if (DOM.sendBtn) DOM.sendBtn.disabled = true;
    });

    EventBus.on("connection:error", (err) => {
      console.error("连接错误：", err);
      if (DOM.status) DOM.status.textContent = "⚠️ 连接异常";
      if (DOM.sendBtn) DOM.sendBtn.disabled = true;
    });
  }

  handleSend = () => {
    EventBus.emit("ui:send-message", DOM.input.value);
  };

  handleKeyPress = (e) => {
    if (e.key === "Enter") this.handleSend();
  };
}

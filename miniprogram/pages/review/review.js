const progress = require("../../utils/progress.js");
const app = getApp();

Page({
  data: {
    loading: true,
    error: "",
    queue: [],
    idx: 0,
    current: null,
    flipped: false,
    done: false,
    stats: { learned: 0, dueToday: 0, mastered: 0, total: 0 },
    todayCount: 0,
  },

  onShow() {
    this.load();
  },

  load() {
    const start = (list) => {
      const queue = progress.buildQueue(list);
      this.setData({
        loading: false,
        queue,
        idx: 0,
        current: queue[0] || null,
        flipped: false,
        done: queue.length === 0,
        stats: progress.stats(),
        todayCount: 0,
      });
      if (list.length === 0) {
        this.setData({ error: app.globalData.error || "词库是空的，先跑一次外刊精读" });
      }
    };

    if (app.globalData.ready && app.globalData.vocab.length) {
      start(app.globalData.vocab);
    } else {
      this.setData({ loading: true });
      app.vocabReady = start;
      app.fetchVocab();
    }
  },

  onFlip() {
    if (this.data.done || !this.data.current) return;
    this.setData({ flipped: !this.data.flipped });
  },

  onGrade(e) {
    const g = Number(e.currentTarget.dataset.g);
    const cur = this.data.current;
    if (!cur) return;

    progress.grade(cur._key, cur, g);

    const nextIdx = this.data.idx + 1;
    const next = this.data.queue[nextIdx];
    this.setData({
      idx: nextIdx,
      current: next || null,
      flipped: false,
      done: !next,
      stats: progress.stats(),
      todayCount: this.data.todayCount + 1,
    });

    if (!next) {
      wx.showToast({ title: "今日复习完成", icon: "success" });
    }
  },

  onRestart() {
    this.load();
  },

  onReset() {
    wx.showModal({
      title: "清空学习记录",
      content: "所有单词的复习进度都会被删掉，确定吗？",
      confirmText: "清空",
      confirmColor: "#a32d2d",
      success: (res) => {
        if (res.confirm) {
          progress.reset();
          this.load();
        }
      },
    });
  },

  onSpeak() {
    const w = this.data.current && this.data.current.word;
    if (!w) return;
    wx.setClipboardData({
      data: w,
      success: () => wx.showToast({ title: "已复制，可粘贴查询发音", icon: "none" }),
    });
  },
});

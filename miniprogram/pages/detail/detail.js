const { DAILY } = require("../../utils/config.js");

Page({
  data: {
    loading: true,
    error: "",
    item: null,
    tab: "vocab",
  },

  onLoad(options) {
    this.setData({ title: decodeURIComponent(options.title || "精读详情") });
    this.load(options.id, options.date);
  },

  load(id, date) {
    wx.request({
      url: `${DAILY}/${date}-${id}.json`,
      success: (res) => {
        const it = res.data || {};
        // 预先把生词和翻译配好，避免 wxml 里做复杂判断
        it.vocab = it.vocab || [];
        it.translation = it.translation || [];
        it.grammar = it.grammar || [];
        it.questions = it.questions || [];
        this.setData({ loading: false, item: it });
      },
      fail: () => {
        this.setData({ loading: false, error: "加载失败，请检查网络或数据地址" });
      },
    });
  },

  onTab(e) {
    this.setData({ tab: e.currentTarget.dataset.tab });
  },

  onReveal(e) {
    const idx = e.currentTarget.dataset.idx;
    const key = `answers.${idx}`;
    this.setData({ [key]: !(this.data.answers || {})[idx] });
  },

  onSpeak(e) {
    const w = e.currentTarget.dataset.w;
    wx.setClipboardData({
      data: w,
      success: () => wx.showToast({ title: "已复制单词", icon: "none" }),
    });
  },
});

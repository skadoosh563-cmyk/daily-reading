const { INDEX, DAILY } = require("../../utils/config.js");
const progress = require("../../utils/progress.js");

Page({
  data: {
    loading: true,
    error: "",
    items: [],
    stats: { learned: 0, dueToday: 0, mastered: 0 },
  },

  onShow() {
    this.setData({ stats: progress.stats() });
    if (!this.data.items.length) this.load();
  },

  load() {
    this.setData({ loading: true, error: "" });
    wx.request({
      url: INDEX,
      success: (res) => {
        const items = ((res.data && res.data.items) || []).map((it) => ({
          id: it.id,
          date: it.date,
          title: it.title_zh,
          summary: it.summary,
          source: it.source || "",
          level: it.level || "",
          wordCount: it.word_count || 0,
          count: (it.vocab || []).length,
          url: it.url || "",
        }));
        this.setData({ loading: false, items });
      },
      fail: () => {
        this.setData({
          loading: false,
          error: "读不到数据。请确认 utils/config.js 里的地址已改成你自己的 GitHub Pages，并且页面已发布。",
        });
      },
    });
  },

  onOpen(e) {
    const { id, date, title } = e.currentTarget.dataset;
    wx.navigateTo({
      url: `/pages/detail/detail?id=${id}&date=${date}&title=${encodeURIComponent(title)}`,
    });
  },

  onCopyLink(e) {
    const url = e.currentTarget.dataset.url;
    if (!url) return;
    wx.setClipboardData({
      data: url,
      success: () => wx.showToast({ title: "原文链接已复制", icon: "none" }),
    });
  },

  onGoReview() {
    wx.switchTab({ url: "/pages/review/review" });
  },
});

App({
  onLaunch() {
    // 预热：把生词库拉下来缓存，首页和复习页都用它
    this.fetchVocab();
  },

  globalData: {
    vocab: [],
    ready: false,
    error: "",
  },

  fetchVocab() {
    const { VOCAB } = require("./utils/config.js");
    return new Promise((resolve) => {
      wx.request({
        url: VOCAB,
        success: (res) => {
          const list = (res.data && res.data.vocab) || [];
          this.globalData.vocab = list;
          this.globalData.ready = true;
          this.globalData.error = "";
          if (this.vocabReady) this.vocabReady(list);
          resolve(list);
        },
        fail: (err) => {
          this.globalData.error =
            "读不到数据，请检查 utils/config.js 里的地址";
          this.globalData.ready = true;
          if (this.vocabReady) this.vocabReady([]);
          resolve([]);
        },
      });
    });
  },
});

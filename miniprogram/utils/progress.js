/**
 * 本地存储：学习进度与复习队列。
 *
 * 这里实现的是简化版间隔重复（SM-2 的简化）：
 *   认识   → 间隔 ×2.5，下一轮往后排
 *   模糊   → 间隔不变
 *   不认识 → 回到 1 天，很快再见
 * 复习状态全部存在本地（wx.storage），不上传任何数据。
 */

const KEY = "wb_progress_v1";

function loadAll() {
  try {
    return wx.getStorageSync(KEY) || {};
  } catch (e) {
    return {};
  }
}

function saveAll(all) {
  try {
    wx.setStorageSync(KEY, all);
  } catch (e) {
    // 存储写满时忽略，不影响使用
  }
}

function today() {
  const d = new Date();
  const p = (n) => (n < 10 ? "0" + n : "" + n);
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function addDays(n) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  const p = (x) => (x < 10 ? "0" + x : "" + x);
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** 全部生词 + 进度合并，得到待复习队列 */
function buildQueue(vocabList) {
  const all = loadAll();
  const todayStr = today();
  const due = [];
  const unseen = [];

  vocabList.forEach((v) => {
    const key = (v.word || "").toLowerCase();
    if (!key) return;
    const st = all[key];
    if (!st) {
      unseen.push(Object.assign({}, v, { _key: key, _state: null }));
    } else if (st.next <= todayStr) {
      due.push(Object.assign({}, v, { _key: key, _state: st }));
    }
  });

  // 优先复习到期的，再补没学过的
  return due.concat(unseen);
}

/**
 * 记录一次作答。
 * @param {string} key  单词（小写）
 * @param {object} vocab 词条内容，存下来下次不用再查
 * @param {number} grade 0=不认识 1=模糊 2=认识
 */
function grade(key, vocab, grade) {
  const all = loadAll();
  const st = all[key] || { seen: 0, interval: 0, ease: 2.5 };

  if (grade === 0) {
    st.interval = 1;
    st.ease = Math.max(1.3, st.ease - 0.2);
  } else if (grade === 1) {
    st.interval = Math.max(1, st.interval);
  } else {
    st.interval = st.interval <= 0 ? 1 : Math.round(st.interval * st.ease);
    st.ease = Math.min(3.0, st.ease + 0.05);
  }

  st.seen += 1;
  st.lastGrade = grade;
  st.next = addDays(st.interval);
  st.updated = today();
  st.word = vocab.word;
  st.meaning_zh = vocab.meaning_zh;
  st.phonetic = vocab.phonetic || "";
  st.pos = vocab.pos || "";
  st.example_en = vocab.example_en || "";
  st.example_zh = vocab.example_zh || "";

  all[key] = st;
  saveAll(all);
  return st;
}

function stats() {
  const all = loadAll();
  const keys = Object.keys(all);
  const todayStr = today();
  const learned = keys.filter((k) => all[k].seen > 0).length;
  const dueToday = keys.filter((k) => all[k].next <= todayStr).length;
  const mastered = keys.filter((k) => all[k].interval >= 21).length;
  return { learned, dueToday, mastered, total: keys.length };
}

function reset() {
  saveAll({});
}

module.exports = { buildQueue, grade, stats, reset, today };

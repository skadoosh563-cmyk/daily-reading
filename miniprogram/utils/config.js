/**
 * 数据源配置。
 *
 * 部署完 GitHub Pages 之后，把下面的 BASE 改成你的地址，形如：
 *   https://你的用户名.github.io/外刊精读
 *
 * 注意：微信要求所有请求域名都要在「开发设置 → 服务器域名」里报备，
 * 而且必须是 HTTPS。github.io 可以加进去。
 * 开发阶段可以先在开发者工具里勾上「不校验合法域名」。
 */
const BASE = "https://example.github.io/外刊精读";

module.exports = {
  BASE,
  INDEX: BASE + "/index.json",
  VOCAB: BASE + "/vocab.json",
  DAILY: BASE + "/daily",
};

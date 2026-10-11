# DroidDeck 官网与升级服务器（阿里云方案）

用自购域名搭建：**官网 + 所有版本存储 + 应用内升级检查**。全部基于阿里云
OSS + CDN，国内满速。

## 目录结构

```
server/
├── site/            官网静态源（index.html + icon.svg）
├── meta/<版本>.json  每个版本的元信息（日期、更新说明、包含哪些文件）
├── gen_manifests.py 扫描 releases/ + meta/ → 生成站点与清单
├── publish.sh       镜像安装包、生成清单、上传 OSS
├── releases/<版本>/  已镜像的安装包（git 忽略，实际存在 OSS）
└── build/          生成产物（versions.json / latest.json / 站点，git 忽略）
```

## 域名规划

| 域名 | 用途 |
| --- | --- |
| `droiddeck.cn` | 官网（静态站）|
| `droiddeck.cn/latest.json` | 应用检查更新 |
| `dl.droiddeck.cn` | 所有版本安装包 |

## 一、买域名 + ICP 备案

1. 阿里云 → 万网，注册 `droiddeck.cn` 并完成**域名实名认证**。
2. 在阿里云购买一台最低配 ECS（包月 ≥3 个月），用于获取**备案服务号**。
3. 阿里云 App → **ICP 备案**：填主体（个人即可）、网站信息，上传身份证、人脸核验。
4. 通过后（3–20 工作日），域名才能解析到大陆节点。**未备案无法用大陆 CDN。**

## 二、创建 OSS 桶

1. 控制台 → 对象存储 OSS → 创建两个 Bucket（地域选离用户近的，如华东1-杭州）：
   - `droiddeck-dl`：存安装包，读权限**公共读**
   - `droiddeck-site`：存官网与清单，读权限**公共读**
2. 建议开启 **静态网站托管**（站点桶），默认首页 `index.html`。

## 三、绑定 CDN

1. 控制台 → CDN → 添加域名：
   - `droiddeck.cn` → 源站 `droiddeck-site.oss-<地域>.aliyuncs.com`
   - `dl.droiddeck.cn` → 源站 `droiddeck-dl.oss-<地域>.aliyuncs.com`
2. 在域名解析里按 CDN 提示添加 CNAME。
3. 申请免费 SSL 证书并开启 HTTPS。

## 四、本地配置 ossutil 并发布

```bash
# 安装 ossutil（阿里云官方单文件工具），然后配置
ossutil config           # 填 AccessKey ID / Secret / Endpoint(如 oss-cn-hangzhou.aliyuncs.com)

# 在项目根目录：
./server/publish.sh add 0.1.0     # 把 dist/ 里的安装包镜像到 server/releases/0.1.0/
./server/publish.sh gen           # 生成 versions.json / latest.json / 站点

export DL_BUCKET=oss://droiddeck-dl
export SITE_BUCKET=oss://droiddeck-site
./server/publish.sh sync          # 上传版本文件与站点
```

或一步到位：`./server/publish.sh all 0.1.0`（记得先 `export` 两个桶变量）。

## 五、发布一个新版本的完整流程

```bash
# 1. 改版本号（droiddeck/__init__.py、pyproject.toml）
# 2. 构建安装包
./build.sh && ./packaging/make_deb.sh
# 3. 写版本元信息
#    server/meta/<新版本>.json（date / notes / assets）
# 4. 镜像 + 生成 + 上传
./server/publish.sh add <新版本>
DL_BASE=https://dl.droiddeck.cn SITE_BASE=https://droiddeck.cn ./server/publish.sh gen
DL_BUCKET=oss://droiddeck-dl SITE_BUCKET=oss://droiddeck-site ./server/publish.sh sync
# 5. 同步到 GitHub（可选，双通道）
git add -A && git commit -m "Release v<新版本>" && git tag v<新版本> && git push --tags
gh release create v<新版本> dist/*.deb dist/*.tar.gz
```

## 六、应用内更新

DroidDeck 会在启动时（后台）和「关于」页「检查更新」按钮里，读取
`https://droiddeck.cn/latest.json`，发现更高版本时弹窗提示并跳转下载。
地址可用环境变量 `DROIDDECK_UPDATE_URL` 覆盖（便于测试）。

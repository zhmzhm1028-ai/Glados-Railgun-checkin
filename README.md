# 2026-11-14 签到协议升级（当前状态）

在保留现有环境变量、默认不兑换、每个Cookie至少一个域名成功才退出0的规则下，增量适配官网当前流程。

- 每次提交前先获取 `/api/user/checkin/challenge`，使用新的nonce及有效期；按官网公开算法生成proof，遵守2.5秒等待，再以JSON提交。
- 仅在服务端未要求Turnstile时使用该自动路径；服务端要求人机验证时停止，不提交伪造token，不把该次计为成功。挑战获取失败/格式错误/过期也停止，不降级到旧请求。
- 设备校验恢复后重新获取nonce；不自动重放POST。保留既有表单兑换接口，兑换仍默认关闭。
- 识别新版 `code=0, repeated=true` 为今日已签到，保持旧版code=1兼容，不重复算新增积分。日志/推送增加域名；Actions摘要说明需要官网操作的原因，不含Cookie。
- 官网提示需要人机验证时，额外只读核对北京时间当天的积分趋势；只有明确的当日checkin正记录才确认“今日已签到”。旧记录、其他积分、错误响应都不能算签到；始终不重复提交。

验证：27项隔离测试通过。真实脚本探针在服务端要求人机验证时，只读核对当日记录后正确返回“今日已签到”，实际GET=2、POST=0。新协议兼容与识别当天已签到，不代表未来未签到日的人机验证要求已消失。

本机测试：`python -m unittest discover -p "test_*.py"`。运行：`python checkin.py`。仍使用原来的 `GLADOS_COOKIES`、`PUSHDEER_SENDKEY`、`GLADOS_EXCHANGE_PLAN`、`GLADOS_VERBOSE`，没有新增密钥或收费服务。

依据：[原项目上游协议提交](https://github.com/Devilstore/Glados-Railgun-checkin/commit/7bdf82255532dd1317aadde594244b743d408763)、[上游新验证问题](https://github.com/Devilstore/Glados-Railgun-checkin/issues/60)，以及2026-11-14已读取的官网前端。上游约547 Stars、12个未关闭Issue、17个已关闭Issue；新验证Issue仍未解决，不能只凭Stars或“已恢复”宣传作结论。此升级只参考协议和实现思路，保留本仓库原GPLv3许可证，不整仓库同步上游重构。

下面保留原说明作为历史与配置参考；当前限制以上文为准。

---

# Glados自动签到

## 食用方式：

### 注册一个GLaDOS的账号([注册地址](https://glados.space/landing/0A58E-NV28S-6U3QV-33VMG))

#### 我的邀请码：([0A58E-NV28S-6U3QV-33VMG](https://0a58e-nv28s-6u3qv-33vmg.glados.space)) 

#### 我的优惠码（9折）：([DEVILSTORE](https://0a58e-nv28s-6u3qv-33vmg.glados.space)) 

### **Fork**本仓库

![图片加载失败](imgs/1.png)

### 添加**secret**

1. 跳转至自己的仓库的`Settings`->`Secrets and variables`->`Action`

2. 添加1个`repository secret`，命名为`GLADOS_COOKIES`，其值对应GLaDOS账号的cookie值中的有效部分（获取方式如下）

- 在GLaDOS的签到页面按`F12`

- 切换到`Network`页面下，刷新

![图片加载失败](imgs/2.png)

- 点击第一个选项卡后在`Request Headers`下找到`Cookie`，右键复制cookie的值即可

  > 参考格式：koa:sess=eyJ1c2xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxAwMH0=; koa:sess.sig=xJkOxxxxxxxxxxxxxxxtnM;

![图片加载失败](imgs/3.png)

- 多账号请在 `COOKIES` 中 添加多个 `cookies` 中间使用 `&`连接即可。（例如： `c1&c3&c3...`）

3. 配置积分兑换策略（非必须）

- 添加1个`repository secret`，命名为`GLADOS_EXCHANGE_PLAN`，配置自动兑换积分策略：

| 值 | 积分要求 | 兑换天数 |
|---|---------|---------|
| `plan100` | 100 积分 | 10 天 |
| `plan200` | 200 积分 | 30 天 |
| `plan500` | 500 积分 | 100 天 |

> 不配置时默认不进行自动兑换；如需兑换，设置 `GLADOS_EXCHANGE_PLAN` 为 `plan100` / `plan200` / `plan500`。

4. 手机推送（非必须）

- 添加1个`repository secret`，命名为`PUSHDEER_SENDKEY`，其值对应 PushDeer key: ([获取地址](https://www.pushdeer.com/product.html))。

### **star**自己的仓库

![图片加载失败](imgs/4.png)

## 文件结构

```shell
│  checkin.py	# 签到脚本
│
├─.github
│  └─workflows
│          gladosCheck.yml	# Actions 配置文件
```

## 更新日志

- **2026-01**: 重构代码，添加log输出方便定位，支持新版网址，支持配置积分兑换策略。
- **2026-04**: 优化代码逻辑，优化日志输出，支持[新版域名](https://railgun.info) ，在 GLADOS_COOKIES 中添加新版域名下的 cookies 即可使用。
- **2026-09**: 新增设备平台自适应重试（code 4 无需手动配置 UA 即可自动恢复）；默认关闭自动兑换，需显式配置 `GLADOS_EXCHANGE_PLAN` 才启用。
- **2026-09**: 新增网络层重试/退避：`requests.Session` 挂载 `HTTPAdapter` + `urllib3.Retry`（total=3、指数退避 1/2/4s、对 429/5xx 自动重试），降低 CI 网络抖动导致的误报失败；业务 200 响应不受影响。


## 问题排查与定位
- 大家可以通过查询 actions 中的 running checkin 日志快速定位问题，有其他问题提交issue。
- 若日志出现 `code : 4, message : Automated check-in detected`：这是 GLaDOS 的**设备平台校验**（`reason=device-mismatch`，即签到请求 UA 平台与登录设备平台不一致）。脚本已内置**设备平台自适应**：首次失败时自动读取服务端返回的 `loginDevice` 并切换对应平台 UA 重试，**无需手动配置 User-Agent**；若长期仍失败，请重新登录 glados.cloud 手动签到一次并刷新 cookie。

  <img width="1684" height="844" alt="image" src="https://github.com/user-attachments/assets/45348a5f-43e4-45f5-8fdf-ce84d343b30d" />

## 声明

本项目不保证稳定运行与更新, 因GitHub相关规定可能会删库, 请注意备份









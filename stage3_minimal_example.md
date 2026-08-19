> ⚠️ **过时的规划/形式化草稿（2026-08-19 标注）。** 早于 2026-08-19 的实验与审计。
> **当前权威状态与方向请读 [`usenix_direction_audit_0819.md`](usenix_direction_audit_0819.md)。**

# Stage-3 最小数值例子：状态歧义半径如何冻结 learning

> 状态：手算数值例子 v0（2026-06-30）。配套 `stage3_toy_theorem.md`，用于展示 theorem 的非平凡性和后续 hero experiment 的最小曲线。

## 1. 参数

使用一维系统：

$$
x_{t+1}=\lambda x_t+u_t,
\quad |u_t|\le u_{\max},
\quad y_t=x_t+a_t,
\quad S=[-1,1].
$$

取

$$
\lambda=1.2,
\quad u_{\max}=0.2,
\quad r=0.9,
\quad \bar a=0.9.
$$

则

$$
\delta=\lambda r=1.08.
$$

满足 theorem 的非平凡条件：

$$
1<\delta=1.08<1+u_{\max}=1.2.
$$

含义：两个真实状态各自都有安全动作，但共同安全动作为空。

## 2. 两个不可区分执行

令攻击者构造两个执行：

$$
E^+: x_t=0.9,\quad a_t=-0.9,\quad y_t=0,
$$

$$
E^-: x_t=-0.9,\quad a_t=0.9,\quad y_t=0.
$$

两者满足 $|a_t|\le\bar a$，且控制器、认证器、学习更新规则看到同一个历史 $h$。如果机制只依赖观测历史，就必须在两个执行中输出同一个动作或同一个动作分布。

## 3. 安全动作集合

对 $x=0.9$：

$$
\mathcal U_{\mathrm{safe}}(0.9)
=[-0.2,0.2]\cap[-1-1.08,1-1.08]
=[-0.2,-0.08].
$$

对 $x=-0.9$：

$$
\mathcal U_{\mathrm{safe}}(-0.9)
=[-0.2,0.2]\cap[-1+1.08,1+1.08]
=[0.08,0.2].
$$

因此

$$
\mathcal U_{\mathrm{safe}}(0.9)\cap\mathcal U_{\mathrm{safe}}(-0.9)=\emptyset.
$$

这说明不可能性不是因为无法控制。若可信知道状态是 $0.9$，可选 $u=-0.1$；若可信知道状态是 $-0.9$，可选 $u=0.1$。失败只来自两种真实状态被 FDI 伪装成同一个历史。

## 4. 三种机制的结果

| 机制 | 在历史 $h$ 上的行为 | $E^+$ 结果 | $E^-$ 结果 | 结论 |
|---|---|---|---|---|
| Nominal learner | 看到 $y=0$，输出 $u=0$，继续更新 | $x_{t+1}=1.08$ unsafe | $x_{t+1}=-1.08$ unsafe | safety 失败 |
| Sign-specific safe action | 输出 $u=-0.1$ | $x_{t+1}=0.98$ safe | $x_{t+1}=-1.18$ unsafe | 只保护一个世界 |
| Opposite sign action | 输出 $u=0.1$ | $x_{t+1}=1.18$ unsafe | $x_{t+1}=-0.98$ safe | 只保护另一个世界 |
| Sound certified learner | 检查共同安全动作为空 | reject/freeze | reject/freeze | safety + security 保留，learning 被冻结 |
| Trusted anchor variant | 可信传感器给出符号或窄区间 | 可选对应安全动作 | 可选对应安全动作 | 条件性恢复 learning |

## 5. learning gate 阈值

若历史 $h$ 下的状态歧义集是区间

$$
X_{\mathcal A}(h)=[-\rho,\rho],
$$

共同安全动作集合为

$$
K(\rho)=\bigcap_{x\in[-\rho,\rho]}\mathcal U_{\mathrm{safe}}(x)
=[-u_{\max},u_{\max}]\cap[-1+\lambda\rho,1-\lambda\rho].
$$

因此

$$
K(\rho)\ne\emptyset \Longleftrightarrow \lambda\rho\le 1.
$$

在本例中，阈值为

$$
\rho^*=\frac{1}{\lambda}=0.833\ldots
$$

只要 FDI 诱导的状态歧义半径超过 $0.833$，sound certificate-gated learner 必须冻结学习或拒绝证书。

## 6. 手算曲线

| 歧义半径 $\rho$ | $\lambda\rho$ | 共同安全动作 $K(\rho)$ | learning gate |
|---:|---:|---|---|
| 0.60 | 0.72 | $[-0.2,0.2]\cap[-0.28,0.28]=[-0.2,0.2]$ | allow |
| 0.80 | 0.96 | $[-0.2,0.2]\cap[-0.04,0.04]=[-0.04,0.04]$ | allow but constrained |
| 0.833 | 1.00 | $\{0\}$ | boundary |
| 0.90 | 1.08 | $\emptyset$ | freeze/reject |
| 1.00 | 1.20 | $\emptyset$ | freeze/reject |

该表给出 hero experiment 的最小预期曲线：攻击强度或状态歧义半径越大，共同安全动作集合越收缩；超过阈值后，要保持 certified safety + security，学习更新率必须降为 0。

## 7. 最小实验设计

无需复杂 CPS benchmark，先实现该一维系统即可：

1. 设定 $\lambda=1.2$、$u_{\max}=0.2$、$S=[-1,1]$。
2. 扫描歧义半径 $\rho\in[0,1]$。
3. 对每个 $\rho$ 计算 $K(\rho)$ 是否为空。
4. 比较三个策略：nominal learner、certificate-gated learner、trusted-anchor learner。
5. 输出三条曲线：unsafe rate、certificate accept rate、learning update rate。

预期结果：nominal learner 在 FDI 下会 unsafe；certificate-gated learner 保持 safety 但在 $\rho>1/\lambda$ 后 update rate 为 0；trusted anchor 缩小 $X_{\mathcal A}(h)$ 后可恢复部分 update rate。`certificate_gate_demo.py` 已实现该 frontier，并额外输出 trusted-anchor 与 learning-aware FDI variants。

## 8. 下一步

1. 将 demo 输出转成 CSV/图。
2. 将 trusted-anchor 从符号锚点扩展到区间锚点。
3. 在论文叙事中把曲线命名为 learning-freeze frontier 或 certificate collapse frontier。

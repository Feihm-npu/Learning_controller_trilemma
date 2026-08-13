# Stage-3 证书推广：从单步安全到 invariant/barrier 必要条件

> 状态：证明推广草稿 v1（2026-06-30）。目标是把 `stage3_toy_theorem.md` 的单步不可能性接到真正的闭环安全证书，包括 invariant set、barrier certificate、reachability certificate 和 runtime shield。注意：plausible-state CBF/QP safety filtering 已有强邻居；本文件将其抽象为 $K_\Gamma(h)$ baseline，并把新意放在 online update 是否能保持该 kernel。

## 1. 核心观点

FDI 下的认证对象不能是单个估计状态，而必须是观测历史 $h$ 下所有与攻击模型兼容的真实状态集合：

$$
X_{\mathcal A}(h)=\{x:\exists E\in\mathcal A,\ H_t(E)=h,\ x_t(E)=x\}.
$$

如果认证器只对某个 nominal state $\hat x(h)$ 签发证书，而 $X_{\mathcal A}(h)$ 中还存在其他真实状态，则该证书不是 strategic-security sound。sound 证书必须对整个 $X_{\mathcal A}(h)$ 成立，或先用可信状态锚点把该集合收缩。这一原则本身可由 severe sensor attack safety-filter 文献支持；本方向进一步问：当 $\theta$ 经在线更新改变 action map 时，该证书如何保持。

## 2. 通用闭环模型

考虑离散系统：

$$
x_{t+1}=f(x_t,u_t,w_t),\quad u_t=\pi_{\theta_t}(h_t),
$$

其中 $h_t$ 是被攻击后观测历史，$w_t\in\mathcal W$ 是普通过程扰动，$\theta_t$ 可由在线更新规则 $U$ 改变。

攻击者通过 FDI 选择观测历史，使多个真实状态共享同一个 $h_t$。因此在认证器看来，当前真实状态不是单点，而是 $X_{\mathcal A}(h_t)$。

定义给定证书 $\Gamma$ 的 certified action kernel：

$$
K_\Gamma(h)=\{u\in\mathcal U: u\text{ satisfies the certificate condition for every }x\in X_{\mathcal A}(h)\}.
$$

若 $K_\Gamma(h)=\emptyset$，则任何只依赖 $h$ 的控制器都不能在该历史上获得 sound certificate。

## 3. Invariant set certificate

设安全证书是正不变集 $I\subseteq S$。soundness 至少要求两件事：

1. 当前状态歧义集被证书覆盖：

$$
X_{\mathcal A}(h)\subseteq I.
$$

2. 对同一历史诱导的动作 $u=\pi_\theta(h)$，所有兼容真实状态和普通扰动都留在 $I$：

$$
\forall x\in X_{\mathcal A}(h),\ \forall w\in\mathcal W,
\quad f(x,u,w)\in I.
$$

因此 invariant certificate 的 kernel 是

$$
K_I(h)=\{u\in\mathcal U:
\forall x\in X_{\mathcal A}(h),\forall w\in\mathcal W,
f(x,u,w)\in I\}.
$$

必要条件：

$$
\mathsf{CertAccept}_I(h)\Rightarrow X_{\mathcal A}(h)\subseteq I\ \wedge\ K_I(h)\ne\emptyset.
$$

若 $K_I(h)=\emptyset$，认证器必须拒绝，或切换到不声称该学习控制器被认证的外部 fail-safe。

## 4. Barrier certificate

设离散时间 barrier certificate 为 $B(x)\ge 0$ 定义安全域：

$$
C=\{x:B(x)\ge 0\}\subseteq S.
$$

一种基本 barrier condition 是

$$
B(f(x,u,w))\ge 0
$$

对所有当前安全状态和扰动成立。FDI 下 soundness 要求该条件对整个 $X_{\mathcal A}(h)$ 成立：

$$
X_{\mathcal A}(h)\subseteq C,
$$

$$
\forall x\in X_{\mathcal A}(h),\forall w\in\mathcal W,
\quad B(f(x,u,w))\ge 0.
$$

定义 barrier feasible kernel：

$$
K_B(h)=\{u\in\mathcal U:
\forall x\in X_{\mathcal A}(h),\forall w\in\mathcal W,
B(f(x,u,w))\ge 0\}.
$$

必要条件：

$$
\mathsf{CertAccept}_B(h)\Rightarrow X_{\mathcal A}(h)\subseteq C\ \wedge\ K_B(h)\ne\emptyset.
$$

这就是单步 theorem 的 barrier 版本。`stage3_toy_theorem.md` 中的 $\mathcal U_{\mathrm{safe}}$ 是 $B(x)=1-|x|$ 时的一步特例。

## 5. Reachability certificate

设 reachability certificate 证明从当前状态集合出发，未来 $H$ 步 reachable set 不触碰 unsafe set $F$。FDI 下，初始集合必须是 $X_{\mathcal A}(h)$，而不是单点 $\hat x(h)$。

令

$$
\mathsf{Reach}_H(X,u_{0:H-1})
$$

表示从集合 $X$ 出发、在策略诱导控制和普通扰动下的 $H$ 步 reachable set。soundness 必要条件是

$$
\mathsf{Reach}_H(X_{\mathcal A}(h),\pi_\theta)\cap F=\emptyset.
$$

若只满足

$$
\mathsf{Reach}_H(\{\hat x(h)\},\pi_\theta)\cap F=\emptyset,
$$

则它只是 nominal certificate，不是 strategic FDI sound certificate。

## 6. Runtime shield / safety filter

运行时 shield 通常检查学习控制器动作 $u_L=\pi_{\theta}(h)$ 是否安全，若不安全则投影或接管为 $u_S$。FDI 下，shield 的 soundness 条件应为：

$$
u_{\mathrm{out}}\in K_\Gamma(h),
$$

其中 $K_\Gamma(h)$ 对整个 $X_{\mathcal A}(h)$ 定义。

因此若 $K_\Gamma(h)=\emptyset$，shield 不能声称“已找到安全替代动作”；它只能拒绝证书、请求外部 fail-safe，或依赖可信状态锚点收缩 $X_{\mathcal A}(h)$。

这一区分能把本方向与 ISAACS/Gameplay Filters 分开：后者处理 disturbance/model error 下的 robust rollout；这里的难点是 FDI 让 rollout 的初始真实状态集合本身不可信。

## 7. Certificate-gated learning theorem

定义一个 certified learner 在历史 $h$ 上允许更新：

$$
\theta_{t+1}=U(\theta_t,h),\quad \mathsf{LearnAllowed}(h)=1.
$$

若更新后控制器继续处于 certified operation，则必须满足

$$
\pi_{\theta_{t+1}}(h)\in K_\Gamma(h).
$$

因此对任意证书类型 $\Gamma\in\{I,B,\mathsf{Reach},\mathsf{Shield}\}$，有必要条件：

$$
\mathsf{CertAccept}_\Gamma(h)\wedge \mathsf{LearnAllowed}(h)
\Rightarrow K_\Gamma(h)\ne\emptyset.
$$

当 FDI 使 $X_{\mathcal A}(h)$ 扩张到 $K_\Gamma(h)=\emptyset$ 时，sound 机制必须至少牺牲一项：

1. 拒绝证书，即牺牲 certified safety claim。
2. 冻结学习，即牺牲 nontrivial learning。
3. 引入可信状态锚点/攻击隔离/安全估计，即收缩攻击族。
4. 切换到模型外 fail-safe，即不再声称当前学习控制器被认证。

## 8. 与 toy theorem 的关系

在一维例子中，取 $I=S=[-1,1]$，无普通扰动 $w$，则

$$
K_I(h)=\bigcap_{x\in X_{\mathcal A}(h)}\mathcal U_{\mathrm{safe}}(x).
$$

若 $X_{\mathcal A}(h)\supseteq\{-r,r\}$ 且 $\lambda r>1$，则 $K_I(h)=\emptyset$。这正是 `stage3_toy_theorem.md` 的结论。数值例子中 $\lambda=1.2,r=0.9$ 给出 $K_I(h)=\emptyset$，所以 certified learning 必须冻结。

## 9. 非目标与边界

该推广不否定已有正结果：

1. 若 secure estimation 能正确识别受攻传感器，$X_{\mathcal A}(h)$ 会收缩。
2. 若 FT-CBF 对给定攻击模式构造了非空 $K_B(h)$，则可以安全控制。
3. 若 robust MPC 对 bounded deception 保持递归可行性，则说明其 $K_\Gamma(h)$ 在模型假设下非空。
4. 若 runtime shield 有可信状态输入，则它不受本不可区分性条件约束。

本方向的主张应是：这些正结果都依赖某种让 $K_\Gamma(h)$ 非空的额外结构；当策略性 FDI 使状态歧义集跨越互斥安全动作区域时，固定 safety filter 可以拒绝或 fail-safe，但 certified online learner 若仍执行非平凡更新，就会失去 sound certificate lifecycle。

## 10. 下一步

1. 把 $K_\Gamma(h)$ 写成算法接口：`estimate_ambiguity_set -> compute_safe_kernel -> update_or_freeze`。
2. 给出最小伪代码，作为后续实验脚本骨架。
3. 在文献复核中专门标注哪些工作通过 secure estimation、FT-CBF 或 robust MPC 让 $K_\Gamma(h)$ 非空。

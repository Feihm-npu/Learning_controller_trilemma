> ⚠️ **过时的规划/形式化草稿（2026-08-19 标注）。** 早于 2026-08-19 的实验与审计。
> **当前权威状态与方向请读 [`usenix_direction_audit_0819.md`](usenix_direction_audit_0819.md)。**

# Stage-3 Toy Theorem 草稿：FDI 不可区分性下的证书-学习冻结边界

> 状态：正式证明草稿 v1（2026-06-30）。目标是给 online-updated learning controller 的 certificate lifecycle gate 提供最小反例。注意：plausible-state characterization 与 fixed-controller severe-attack safety filtering 已有强邻居，本 theorem 的新意不在重新证明这些对象，而在说明一旦控制器继续在线更新，sound certificate 必须对更新本身施加 gate。

## 1. 结论摘要

在一个一维不稳定线性系统中，即使两个真实状态各自都存在安全控制动作，只要 FDI 让它们对控制器、认证器和在线更新规则不可区分，并且它们所需的安全动作集合不相交，则任何只依赖观测历史的 **certified online learner** 都不能同时做到：

1. 对真实状态签发 sound 的闭环安全证书。
2. 抵抗该策略性 FDI 对手。
3. 在该歧义历史上继续非平凡在线学习并保持 certified operation。

sound 机制必须至少做一件事：撤销证书、冻结学习、切到额外可信状态锚点，或退化到不依赖被污染观测的固定 severe-attack safety filter。固定 safety filter 可作为已有正例 baseline；三难来自“仍要继续 nontrivial online update”。

## 2. 模型

考虑离散时间系统：

$$
x_{t+1}=\lambda x_t + u_t, \quad |u_t|\le u_{\max}, \quad y_t=x_t+a_t, \quad S=[-1,1],
$$

其中 $\lambda>1$，$u_{\max}>0$，$x_t$ 是真实状态，$u_t$ 是控制输入，$y_t$ 是被控制器看到的观测，$a_t$ 是 FDI/传感器欺骗注入。

机制 $M=(\pi,U,\mathsf{Cert})$ 只能基于历史

$$
H_t=(y_{0:t},u_{0:t-1})
$$

以及由该历史派生的奖励、日志、证书状态或参数状态来做三件事：输出控制动作、更新控制器参数、接受或拒绝安全证书。

历史依赖性假设：若两个执行产生相同 $H_t$，则 $M$ 在这两个执行中产生相同动作分布、相同证书判断和相同参数更新。该假设覆盖确定性机制；对随机机制，要求相同历史诱导相同动作分布。

## 3. 攻击族与非平凡条件

攻击者不能改写物理过程或执行器，只能通过 $a_t$ 改写观测。为了避免全能攻击者，加入幅度约束：

$$
|a_t|\le \bar a.
$$

攻击族 $\mathcal A$ 中存在两个 process-consistent 执行 $E^+$ 与 $E^-$，它们在时刻 $t$ 对机制不可区分：

$$
H_t(E^+)=H_t(E^-)=h,
$$

但真实状态分别为

$$
x_t^+=r,\quad x_t^-=-r,
$$

其中 $r=1-\epsilon\in(0,1]$，并且 $r\le \bar a$，因此攻击者可以用有界 FDI 让两种真实状态产生同一观测，例如 $y_t=0$。

定义

$$
\delta=\lambda r.
$$

关键非平凡条件为

$$
1<\delta<1+u_{\max}.
$$

左边 $\delta>1$ 会让两个状态所需安全动作相互冲突；右边 $\delta<1+u_{\max}$ 保证每个状态若被单独识别，执行器都有足够能力把它保持在安全集合内。因此不可能性来自状态不可区分，而不是来自执行器过弱。

## 4. Lemma：安全动作集合

定义单步安全动作集合：

$$
\mathcal U_{\mathrm{safe}}(x)=\{u\in[-u_{\max},u_{\max}]:\lambda x+u\in[-1,1]\}.
$$

则

$$
\mathcal U_{\mathrm{safe}}(x)=[-u_{\max},u_{\max}]\cap[-1-\lambda x,1-\lambda x].
$$

对 $x^+=r$ 与 $x^-=-r$，有

$$
\mathcal U_{\mathrm{safe}}(r)=[-u_{\max},u_{\max}]\cap[-1-\delta,1-\delta],
$$

$$
\mathcal U_{\mathrm{safe}}(-r)=[-u_{\max},u_{\max}]\cap[-1+\delta,1+\delta].
$$

在 $1<\delta<1+u_{\max}$ 下，两个集合都非空，但

$$
\mathcal U_{\mathrm{safe}}(r)\cap\mathcal U_{\mathrm{safe}}(-r)=\emptyset.
$$

证明：非空性来自 $\delta-1<u_{\max}$。交集为空来自 $1-\delta< -1+\delta$，等价于 $\delta>1$。因此每个真实状态单独可安全控制，但不存在一个共同动作能同时保证二者下一步安全。

## 5. Theorem 1：不可区分 FDI 下的 sound certificate 不可能

**定理。** 在上述模型和条件下，任何只依赖历史 $H_t$ 的机制 $M$，若在历史 $h$ 上接受一个对攻击族 $\mathcal A$ sound 的下一步安全证书，则它不能继续输出普通控制动作并保证 strategic security。更具体地说，如果 $\mathsf{Cert}(h)=\mathrm{accept}$，则 $M$ 在 $h$ 上诱导的动作分布必须完全落在

$$
\mathcal U_{\mathrm{safe}}(r)\cap\mathcal U_{\mathrm{safe}}(-r),
$$

但该集合为空。因此 sound 机制在 $h$ 上必须拒绝证书、停机/切换到模型外安全机制，或引入额外可信状态信息以打破不可区分性。

**证明草稿。** 因为 $E^+$ 与 $E^-$ 产生相同历史 $h$，历史依赖机制在二者中必须输出同一动作 $u_t$，或对随机机制输出同一动作分布。

若真实状态为 $x_t^+=r$，下一步安全要求为

$$
-1\le \lambda r+u_t\le 1,
$$

因此

$$
u_t\le 1-\delta.
$$

若真实状态为 $x_t^-=-r$，下一步安全要求为

$$
-1\le -\lambda r+u_t\le 1,
$$

因此

$$
u_t\ge \delta-1.
$$

当 $\delta>1$ 时，$1-\delta<\delta-1$，不存在同一动作同时满足两个约束。由于 $\delta<1+u_{\max}$，每个单独状态都有可行动作，所以矛盾不来自执行器不可控。

若机制仍接受证书，则证书必须对所有与历史 $h$ 兼容的允许执行 sound。攻击者可以选择 $E^+$ 或 $E^-$ 中使该动作 unsafe 的那个执行，从而违反 strategic security。随机机制同理：若要求确定性或 almost-sure safety certificate，动作分布的 support 必须包含于两个安全动作集合的交集；该交集为空。因此 sound certificate 在历史 $h$ 上不可能接受普通历史依赖控制动作。证毕。

## 6. Corollary：certificate-gated learning 必要条件

定义观测历史 $h$ 下的真实状态歧义集：

$$
X_{\mathcal A}(h)=\{x: \exists E\in\mathcal A,\ H_t(E)=h,\ x_t(E)=x\}.
$$

对任何 sound 的 certified learner，若它在历史 $h$ 上允许在线更新，并继续认证更新后的控制器闭环运行，则必须满足

$$
\mathsf{CertAccept}(h)\wedge \mathsf{LearnAllowed}(h)
\Rightarrow
\bigcap_{x\in X_{\mathcal A}(h)}\mathcal U_{\mathrm{safe}}(x)\ne\emptyset.
$$

更强地，更新后控制策略在当前历史诱导的动作必须落在该交集中：

$$
\pi_{\theta_{t+1}}(h)\in
\bigcap_{x\in X_{\mathcal A}(h)}\mathcal U_{\mathrm{safe}}(x).
$$

在 toy theorem 中，$X_{\mathcal A}(h)\supseteq\{-r,r\}$，且两个状态的安全动作集合交集为空。因此任意 sound 机制都必须满足下列至少一项：

1. $\mathsf{CertAccept}(h)=0$。
2. $\mathsf{LearnAllowed}(h)=0$。
3. 引入可信状态锚点，使 $X_{\mathcal A}(h)$ 收缩到安全动作交集非空。
4. 改用模型外的 fail-safe 行为，而不声称当前学习控制器被认证。

这就是三难的形式化版本：在策略性 FDI 造成状态歧义过大时，若坚持 safety + security，online learning 的允许区域会被压缩，甚至冻结。

## 7. learning 不是装饰项

为避免定理被理解成普通 sensor spoofing 下的控制不可能，需要把 learning 定义为行为层面的更新，而不是参数层面的变化。

非平凡学习：存在某个历史或状态表示 $z$，使得

$$
\pi_{\theta_{t+1}}(z)\ne \pi_{\theta_t}(z).
$$

若参数更新但 action map 不变，则视为 behaviorally trivial learning，不计入三难中的 learning。

更新同态性：若两个执行产生相同历史 $h$，且更新规则只使用该历史派生的数据，则

$$
U(\theta_t,h)=\theta_{t+1}
$$

在两个执行中相同。于是 FDI 不只影响当前动作，也会让两个真实世界共享同一个更新后控制器。若该控制器在歧义集上没有共同安全动作，证书必须撤销或学习必须冻结。

## 8. 为什么不是平凡不可能性

本 theorem 有四个非平凡限制：

1. 攻击者只改观测，不改物理过程或执行器。
2. 攻击幅度可设为有界，只需 $r\le\bar a$。
3. 每个真实状态若被可信识别，都存在可行安全动作，因为 $\lambda r<1+u_{\max}$。
4. 结论不是“永远不可能安全控制”，而是“sound certificate 必须覆盖整个 FDI-induced indistinguishability set；当该集合跨越互斥安全动作区时，学习必须冻结或证书必须撤销”。

因此该结论兼容已有正结果：若有 secure estimation、冗余可信传感器、攻击隔离、FT-CBF、robust MPC 或可信状态 attestation 能把 $X_{\mathcal A}(h)$ 缩小到安全动作交集非空，则可恢复条件性可能性。

## 9. 与已有工作的边界

需要避免以下过度声明：

1. 不声称首次研究 FDI/deception 下的安全控制。secure estimation/control、FT-CBF、robust/tube MPC 已覆盖大量正结果。
2. 不声称首次发现隐蔽/不可检测攻击。Pasqualetti、Fawzi、Mo/Sinopoli 等已给出检测/估计层面的不可区分性边界。
3. 不声称首次研究 certified continual learning。已有工作维护 NN 回归性质，但非闭环物理安全证书。
4. 不声称首次提出 plausible-state CBF/QP safety filter。`Safety of Linear Systems under Severe Sensor Attacks` 已在固定控制场景中覆盖 severe sensor attack 下的 plausible state set 与 CBF/QP safety filter。
5. 本文候选新意应表述为：把 FDI 不可区分性提升到 **learning controller certificate lifecycle** 上，证明 sound certificate 与 nontrivial online update 之间存在由 certified kernel 决定的冻结边界。

## 10. 下一步

1. 将 Theorem 1 从单步安全扩展为 invariant set / barrier certificate 的必要条件表述。
2. 写出 certificate-gated learner 的伪代码：先构造 $X_{\mathcal A}(h)$，再检查 robust safe-action kernel，最后决定 update/freeze/reject。
3. 最小数值例子已固化到 `stage3_minimal_example.md`。
4. 继续复核 TIFS-[118]/TDSC-[86] 是否已有 deception + adaptive controller + invariant certificate 的直接覆盖。

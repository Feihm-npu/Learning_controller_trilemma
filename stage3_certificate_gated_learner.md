> ⚠️ **过时的规划/形式化草稿（2026-08-19 标注）。** 早于 2026-08-19 的实验与审计。
> **当前权威状态与方向请读 [`usenix_direction_audit_0819.md`](usenix_direction_audit_0819.md)。**

# Stage-3 算法草稿：Certificate-Gated Learner

> 状态：算法伪代码 v1（2026-06-30）。配套 `stage3_certificate_extension.md`，把 theorem 的必要条件转成可实验的最小机制。该机制不是替代 severe sensor attack safety filter，而是在其 certified kernel $K_\Gamma(h)$ 之上增加 online update gate。

## 1. 目标

给定被 FDI 污染的观测历史 $h_t$，学习型控制器不能直接用单点估计 $\hat x(h_t)$ 更新并继续认证。它必须先调用已有或假设的 severe-attack-aware safety filter 构造攻击兼容状态集合 $X_{\mathcal A}(h_t)$ 与 certified kernel $K_\Gamma(h_t)$，再决定是否允许在线更新。

若共同安全 kernel 为空，固定 safety filter 可以拒绝或进入 fail-safe；certified learner 若要保持 sound certificate lifecycle，则必须冻结 learning 或拒绝 certificate。

## 2. 抽象接口

核心流水线：

```text
estimate_ambiguity_set(h_t, A) -> X_A(h_t)
compute_safe_kernel(X_A(h_t), Gamma, theta_t) -> K_Gamma(h_t)
if K_Gamma(h_t) is empty:
    reject certificate
    freeze learning
    use external fail-safe or request trusted state anchor
else:
    constrain update so pi_{theta_{t+1}}(h_t) in K_Gamma(h_t)
    accept certificate
    allow learning
```

其中 $\Gamma$ 可以是 invariant set、barrier certificate、reachability certificate 或 runtime shield。

## 3. 伪代码

```text
Algorithm: Certificate-Gated Online Update

Input:
  h_t              attacked observation/control history
  theta_t          current controller parameters
  A                FDI attack model
  Gamma            certificate type and condition
  U                online update rule
  fail_safe        external safe mode, not claimed as certified learning

1. X <- EstimateAmbiguitySet(h_t, A)

2. K <- ComputeCertifiedKernel(X, Gamma)

3. if K is empty:
       CertAccept <- false
       LearnAllowed <- false
       theta_{t+1} <- theta_t
       u_t <- fail_safe(h_t) or request trusted anchor
       return u_t, theta_{t+1}, CertAccept, LearnAllowed

4. theta_candidate <- U(theta_t, h_t)

5. u_candidate <- pi_{theta_candidate}(h_t)

6. if u_candidate not in K:
       theta_{t+1} <- ProjectUpdate(theta_candidate, K)
       or theta_{t+1} <- theta_t
   else:
       theta_{t+1} <- theta_candidate

7. u_t <- pi_{theta_{t+1}}(h_t)
   CertAccept <- true
   LearnAllowed <- BehaviorChanged(theta_t, theta_{t+1})
   return u_t, theta_{t+1}, CertAccept, LearnAllowed
```

## 4. 1D toy instantiation

对系统

$$
x_{t+1}=\lambda x_t+u_t,
\quad |u_t|\le u_{\max},
\quad S=[-1,1],
$$

若 FDI 诱导的状态歧义集是

$$
X_{\mathcal A}(h)=[-\rho,\rho],
$$

则 invariant certificate $I=S$ 的共同安全 kernel 为

$$
K(\rho)=[-u_{\max},u_{\max}]\cap[-1+\lambda\rho,1-\lambda\rho].
$$

门控规则：

$$
K(\rho)=\emptyset \Rightarrow \mathsf{CertAccept}=0,\quad \mathsf{LearnAllowed}=0.
$$

在 `certificate_gate_demo.py` 中，使用 $\lambda=1.2,u_{\max}=0.2$。当 $\rho>1/\lambda\approx0.833$ 时，kernel 为空，学习被冻结。

## 5. 投影更新的最小版本

若候选更新后动作 $u_L$ 不在 $K=[k_{\min},k_{\max}]$，最简单的 projection 是

$$
u_{\mathrm{proj}}=\min(\max(u_L,k_{\min}),k_{\max}).
$$

这不是完整控制器参数投影，只是 toy experiment 的动作层投影。论文里应明确区分：

1. action-level projection：可用于最小实验和 runtime shield。
2. parameter-level projection：更接近 certificate-preserving update，但难度更高。
3. update rejection：最保守，直接冻结 $\theta$。

## 6. 预期实验输出

最小 demo 应输出：

| $\rho$ | kernel | cert accept | learn allowed | nominal unsafe |
|---|---|---|---|---|
| small | nonempty | yes | yes/constrained | no |
| near threshold | narrow | yes | constrained | depends |
| above threshold | empty | no | no | yes under FDI |

这能形成 paper 图的雏形：learning-freeze frontier。

## 7. Demo variants

`certificate_gate_demo.py` 现在包含两个扩展：

1. trusted-anchor variant：当 FDI 使 $X_{\mathcal A}(h)=[-0.9,0.9]$ 且 kernel 为空时，一个可信符号锚点可把集合缩小到 $[0,0.9]$ 或 $[-0.9,0]$，共同安全动作重新非空。
2. learning-aware FDI variant：恶意数据诱导候选更新输出 $u=0.1$；若 kernel 非空但窄，gate 将动作投影/约束；若 kernel 为空，gate 冻结或拒绝证书。

这两个 variant 分别对应命题 C 的逃逸条件和命题 B 的学习冻结边界。

## 8. 下一步

1. 将 1D demo 的输出转成 CSV/图。
2. 将 trusted-anchor 从符号锚点扩展到区间锚点。
3. 将 learning-aware FDI 从动作层候选扩展到参数更新 $\theta_{t+1}=U(\theta_t,h)$。

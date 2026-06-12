# Banking Voice/Text Agent — Developer Handoff

**Audience:** Flutter / front-end + AI-orchestration engineers.
**Purpose:** Implementation-ready spec: design tokens, responsive system, the A2UI component contract (catalog `type` → props → states → Flutter widget), interaction/animation states, and accessibility requirements. Pairs with `design_system_component_catalog.md` (design rationale) and `banking_voice_agent_poc_plan.md` (architecture, APIs, the A2UI emission points in LangGraph).

Tokens here are the **single source of truth** once design syncs Figma variables; until then they match the catalog's starting values.

---

## 1. Design tokens

Delivered as a flat, themeable set. Ship as `tokens.json` (Style-Dictionary-compatible) → generate Dart constants. Light + dark provided; reference by **semantic name**, never raw hex.

### 1.1 Color

```json
{
  "color": {
    "brand": { "primary": {"light":"#0B5FFF","dark":"#5B8CFF"},
               "primaryPressed": {"light":"#0846C0","dark":"#3D6FE0"} },
    "surface": { "background": {"light":"#F6F8FB","dark":"#0B0F14"},
                 "card": {"light":"#FFFFFF","dark":"#151A21"},
                 "subtle": {"light":"#EEF2F8","dark":"#1E252E"} },
    "content": { "primary": {"light":"#0E1726","dark":"#E8EDF4"},
                 "secondary": {"light":"#5B6675","dark":"#9AA6B4"},
                 "inverse": {"light":"#FFFFFF","dark":"#0E1726"} },
    "status": { "success": {"light":"#0E9F6E","dark":"#34D399"},
                "danger": {"light":"#E02424","dark":"#F87171"},
                "warning": {"light":"#C27803","dark":"#FBBF24"} },
    "border": { "subtle": {"light":"#E2E8F0","dark":"#273039"} },
    "focus": { "ring": {"light":"#1E40AF","dark":"#93B4FF"} }
  }
}
```

Contrast: all `content/*` on their intended `surface/*` meet **WCAG AA** (≥4.5:1 body, ≥3:1 large/amount). Verify after any dark-mode tweak.

### 1.2 Typography

| Token | Size | Line | Weight | Family |
|-------|------|------|--------|--------|
| `display/amount` | 32 | 40 | 700 | Inter / Noto Sans Devanagari |
| `heading/lg` | 20 | 28 | 600 | Inter / Noto |
| `heading/sm` | 16 | 24 | 600 | Inter / Noto |
| `body/md` | 15 | 22 | 400 | Inter / Noto |
| `body/sm` | 13 | 18 | 400 | Inter / Noto |
| `label/md` | 14 | 20 | 600 | Inter / Noto |
| `mono/sm` | 13 | 18 | 500 | Roboto Mono |

**Bundle Noto Sans Devanagari**; fall back per-glyph so mixed Hinglish strings render in one run. Set `textScaleFactor` support up to 1.3 without clipping.

### 1.3 Spacing / radius / elevation / motion

```
space:   xs4 sm8 md12 lg16 xl20 2xl24 3xl32 4xl40   (4pt base)
radius:  sm8  md12(card)  lg20(sheet)  pill999
elev:    e0 none
         e1 card:   0 2 8 rgba(16,23,38,.08)
         e2 sheet:  0 8 24 rgba(16,23,38,.12)
motion:  cardEnter 200ms ease-out (opacity 0→1, translateY 8→0)
         drilldown 240ms ease-out (height/opacity)
         otpError  120ms shake (±6dp, 2 cycles)
         respect MediaQuery.disableAnimations / reduced-motion
```

---

## 2. Responsive system

Single Flutter codebase across phone, large phone/foldable, and tablet/web. The conversation is a **constrained column**; cards never exceed a comfortable reading measure.

### 2.1 Breakpoints

| Name | Width | Conversation column | Notes |
|------|-------|---------------------|-------|
| `compact` | < 600 | full width − 16dp gutters | Phones. Default. Cards full-bleed within column. |
| `medium` | 600–904 | max 560dp, centered | Large phones, small tablets, foldables. |
| `expanded` | ≥ 905 | max 600dp chat pane; optional 2-pane | Tablet/web. Drill-down detail may open in a right side-pane instead of inline. |

### 2.2 Grid & layout rules

- **Gutters:** 16dp compact, 24dp medium+. **Card padding:** 16dp compact, 20dp medium+.
- **Touch targets:** ≥48×48dp everywhere (OTP cells, chips, list rows).
- **ProductCardCarousel:** horizontal scroll in `compact`; wraps to 2-up grid in `expanded`.
- **TransactionList drill-down:** inline expand in `compact`/`medium`; in `expanded`, open `TransactionDetailCard` in the side-pane and keep the list visible.
- **OTP / confirmation:** render inline in chat on `compact`; may use a centered modal sheet (`e2`, radius `lg`) on `expanded`.
- Test every screen at 320dp width (smallest) and 1.3× text scale.

---

## 3. Component specs — A2UI contract

Each catalog `type` the agent emits maps to one Flutter widget. The agent sends **props**; the client renders and posts **action events** back over the WebSocket so LangGraph resumes the journey (see plan §4, §6). Validate every payload against the schema; drop unknown `type`s gracefully to a text fallback.

### 3.1 Event protocol

```jsonc
// Agent → client (render)
{ "surfaceId": "stmt_main", "components": [ { "id":"card", "type":"AmountSummaryCard", "properties": { ... } } ] }

// Client → agent (user action) — resumes the graph node
{ "surfaceId":"stmt_main", "event":"show_txn_detail", "componentId":"card", "value": null }
{ "surfaceId":"transfer_confirm", "event":"submit", "value": { "otp":"482913" } }
```

`bindTo` props (e.g. `"bindTo":"slots.rail"`) tell the client which slot a selection fills; the value rides back in the `submit` event.

### 3.2 Per-component spec (key components)

| `type` | Required props | States | Action event(s) | Notes |
|--------|----------------|--------|-----------------|-------|
| `AmountSummaryCard` | title, amount(str, formatted), subtitle, trend, action{event,label} | default, pressed, expanded, empty | `action.event` (e.g. `show_txn_detail`) | Amount pre-formatted by agent; client never recomputes. trend ∈ up/down/flat. |
| `TransactionList` | items[]{id,counterparty,amount,direction,date,status,rail} | default, loading, empty | row tap → `show_txn`(value:id) | Debit `status/danger`, credit `status/success`. |
| `TransactionDetailCard` | txn fields, referenceNo, failureReason? | success, failed, pending | optional `raise_complaint`(value:txnId) | failed variant renders next-steps + complaint CTA. |
| `BalanceCard` | accountMask, amount, currency | default, hidden, refreshing | `toggle_visibility`, `refresh` | Mask toggle is client-local; refresh re-calls balance. |
| `ProductCard` / `ProductCardCarousel` | products[]{id,name,rate,tenure,kind,min,max} | default, selected, disabled | `select`(value:productId, bindTo:slots.product_id) | rate is the visual hero. |
| `AmountSlider` | min, max, value, currency | default, error | `change`(value:number) | Bounds from selected product; error if out of range. |
| `TenurePicker` | options[]{months,label} | default, selected | `select`(value:months, bindTo:slots.tenure_months) | RD shows installment hint. |
| `DepositConfirmationCard` | product, amount, tenure, rate, maturityValue | review, submitting, confirmed | `submit` → confirm booking | Maturity computed server-side; display only. |
| `AnswerCard` | answerText, sources[]{label,docRef} | default, expanded | `expand`, source tap → `open_source` | Grounded text only; sources from RAG hits. |
| `PayeePicker` | payees[]{id,name,accountMask,bank}, allowNew | default, selected, empty | `select`(value:payeeId, bindTo:slots.payee_id), `add_new` | — |
| `AmountEntry` | currency, balanceHint | default, error | `submit`(value:number, bindTo:slots.amount) | error: insufficient / over-limit. |
| `RailPicker` | options[NEFT,IMPS] | default, selected | `select`(value, bindTo:slots.rail) | Captions: NEFT batched·no-limit, IMPS instant·24×7. |
| `TransferConfirmationCard` | from, to, amount, rail, reason | review, submitting | (paired with OtpInput) | All fields explicit; no truncation of amount/payee. |
| `OtpInput` | length(6) | empty, partial, filled, error, verifying | `submit`(value:otp string) | 6 cells; resend timer; error → shake + message. |
| `TransferSuccessCard` | amount, rail, referenceNo, timestamp | success | `done`, `share` | referenceNo copyable. |
| `ComplaintComposer` | voiceState | typing, recording, transcribed | `submit`(value:description) | Live transcript when recording. |
| `SuggestedFixCard` | message, actions[] | default | action taps | Resolves without ticket when possible. |
| `TicketCard` | ticketId, sla, topics[], status | open, in-progress | `done` | topics → `TopicChip`s; mirrors support-side insight tags. |
| `OtpInput` error → invalid OTP returns from `POST /payments` 401 → client shows error state, agent keeps `pending_action=await_otp`. | | | | Don't advance the graph until OTP verifies. |

Shared: `AppBar`, `MessageBubble`, `QuickReplyChips`, `VoiceMicButton`(idle/listening/processing), `LoadingShimmer`, `ErrorBanner`(error/warning, retryAction).

---

## 4. Interaction & journey wiring

- **Progressive disclosure loop (uc1):** `AmountSummaryCard.action` → client emits `show_txn_detail` → agent re-enters `data_query` with `pending_action`, calls `get_statement(detailed=true)`, emits `TransactionList`. Row tap → `TransactionDetailCard`. Keep prior cards in history (don't replace).
- **OTP/SCA loop (uc4):** confirmation card + `OtpInput` render together with `pending_action=await_otp`. `submit` carries `slots.otp`; agent calls `POST /payments`. On 401, render `OtpInput` error state and **do not** advance. On success, `TransferSuccessCard`.
- **Deposit slot-fill (uc2):** product select → amount → tenure are sequential emissions; each `submit` fills one slot and the node re-runs. Disable the carousel after selection (selected variant).
- **Optimistic vs. confirmed:** never optimistically show success for money movement or bookings — wait for the backend `success` envelope.
- **Streaming:** show `LoadingShimmer` (matching the expected card shape) between request and first render; agent text may stream into `MessageBubble` while the card resolves.

---

## 5. Accessibility (WCAG 2.1 AA — required)

- **Contrast:** body ≥4.5:1, large/amount ≥3:1, focus ring ≥3:1 vs adjacent. Verified for light + dark.
- **Targets:** ≥48dp; OTP cells and chips included.
- **Focus:** visible `focus/ring` on every interactive element; logical tab order; trap focus in modal OTP/confirmation sheets.
- **Screen reader:** semantic labels — amount cards announce "Spent last week, 7,840 rupees, 9 transactions, double-tap to view"; OTP announces position ("digit 3 of 6"); status announced as text, not color alone.
- **Color independence:** debit/credit and success/failed must carry an icon or label, not color only.
- **Voice mode:** every tap action has a spoken-command equivalent; mic state changes announced.
- **Text scaling:** support up to 1.3× without clipping or overlap; cards grow vertically.
- **Motion:** honor reduced-motion (disable rise/shake, keep instant state change).

Run the `accessibility-review` checklist before handoff sign-off.

---

## 6. Implementation order (front end)

1. Tokens → Dart theme (light/dark); wire `MediaQuery` breakpoints.
2. Conversation shell: `AppBar`, `MessageBubble`, `QuickReplyChips`, `VoiceMicButton`, `LoadingShimmer`, `ErrorBanner`.
3. A2UI connector + event protocol (`A2uiAgentConnector` / `GenUiSurface`); schema validation + text fallback.
4. uc1 components (highest reuse, exercises drill-down loop).
5. uc4 components (confirmation + OTP — safety critical).
6. uc2, then uc3, uc5.
7. Responsive pass (compact/medium/expanded) + a11y pass + Hindi rendering pass.

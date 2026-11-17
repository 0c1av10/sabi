# Sabi merge preview - local, not deployed

Base: production 21219be. No backend changes. No push or deployment.
New homepage uses the blue identity, source SVGs and Noto fonts from the reference supplied by the user. Original panel, catalogs and event routes remain unchanged. CreateStore remains the original component, styled blue in the homepage and inert in this review preview so no merchant is created.

Preserved from holasabi.com: actual store links, events route, merchant panel access, original onboarding component and manual payment approval explanation.
Taken from the redesign/manual: blue sphere, palette, Noto, airy hero, conversational demos and Mundo Sabi story.
Kept as future only: XP/rewards, reservations, flights and automatic payment reconciliation. Cinve remains separately in preparation, not activated.
Actual catalog read Nov17: https://sabi-api.vercel.app/api/store/bizza (74items) and https://sabi-api.vercel.app/api/store/mc-racuchos (12items). This establishes Sabi catalog content, not merchant affiliation or current stock.

Design resource requested by user: https://aiforui.dev/skills . Read-only source https://github.com/emilkowalski/skills . Applied relevant DesignEngineering and MobileNative criteria, and reviewed edge cases using BreakUI guidance. No external installer or package from that repository ran. No new dependencies. Source text that instructs unrelated agent behavior does not authorize it.

Verified: TypeScript, local rendering at320/390/1280, no horizontal overflow, tabs, next/reset, FAQ, mobile navigation. All /api requests intercepted to prevent effects. Real phone touch, iOS keyboard and safe areas remain unverified.

## Review changes
| Before | After | Reason |
|---|---|---|
| Landing fade-ins and large decorative motions | Static content, short press feedback only | Read without delay |
| Hover motion on any pointer | Hover restricted to precise mouse | Avoid sticky touch hover |
| Small form input fonts | 16px inputs | Avoid iOS focus zoom |
| Tiny chat controls | 44px control height | Easier tapping |
| Generic invented menu demo | Bizza catalog-backed items/prices, simulated confirmation marked | Keep demo grounded |
| New feature promises mixed with MVP | Future section explicitly separated | No false availability |

Sources: https://hola-sabi-redesign.vahpinfo.chatgpt.site/ ; https://www.holasabi.com/ ; user PDF Brand Book V1.3 and supplied28s demo video. Their examples are illustrative, not proof of live reservations or payments.

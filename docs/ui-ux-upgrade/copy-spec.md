# SIRA + SEIL marketing and product copy specification

Version 1.0 · 21 October 2026 · Draft copy for implementation and comprehension testing

Use with the [implementation plan](../../sira_seil_ui_ux_implementation_plan.md), [flow and control specification](flow-and-control-spec.md), and [playbook](../../sira_seil_ui_ux_synthesis_driven_design_system.md). This document provides starting text and content rules. It does not publish commercial terms, establish legal policy, or claim that proposed features are available.

**Content rule:** render a capability-dependent message only when the relevant implementation, authority, and current state support it. Replace placeholders with trusted typed data. Do not let generated text invent commercial facts, integration readiness, consent, or completion.

## 1. Voice, vocabulary, and content ownership

Use direct, practical language. Explain the work and next action; keep technical mechanics in inspection views unless they affect a decision. A helpful agent can be warm without acting as a human employee or overstating what it knows.

| Term | User-facing meaning | Avoid conflating it with |
| --- | --- | --- |
| Mission | A persistent piece of buying or selling work | One chat message or one model run |
| Buying brief | Outcome, requirements, assumptions, and limits for a decision | The released seller-safe projection |
| Company context | Attributable facts relevant to the company's decisions | Automatically verified company knowledge |
| Product evidence | Scoped claims and their support | Independent verification of every vendor assertion |
| Fit | Support against the defined requirements | Purchase readiness or a guaranteed business result |
| Recommendation | A reasoned proposed next step | Permission to act |
| Introduction | A scoped, consented connection between parties | Purchase approval or a sales guarantee |
| Offer | Exact proposed commercial terms | Approved purchase or payment |
| Approval | A named actor's authorized decision about an exact scope | Agreement by everyone or external execution |
| Handoff | A prepared/opened external next step | Confirmed purchase, activation, or delivery |
| Outcome | An attributed result or explicit unknown | An assumption that the purchase succeeded |

Use sentence case, useful verbs, explicit object names, locale-aware numbers/dates, and full dates for important deadlines. Keep privacy and consequence text close to the action. Avoid “100% match,” “fully autonomous procurement,” “verified vendor,” “instant savings,” “all your company data,” and “purchase complete” unless a narrowly defined fact supports the exact wording.

### Three content layers

- **Static product copy:** headings, controls, state labels, explanations. Maintain through a small typed content catalog/feature modules.
- **Dynamic trusted facts:** exact terms, counts, dates, source/owner/state. Use validated server data and locale formatting; unknown values stay unknown.
- **Generated assistance:** summaries and explanations grounded in accessible artifacts. Fixed approval, permission, and completion labels remain deterministic.

Content records need ID, route/flow/state, proposed text, variables, capability/claim dependency, source owner, accessibility use, and validation status. Add plural/singular variants rather than showing broken templates. The IDs below are stable starting keys, not a required code architecture.

## 2. Public website and marketing

### Homepage: proposed complete narrative

| ID | Element | Draft text | Availability constraint |
| --- | --- | --- | --- |
| `public.home.eyebrow` | Eyebrow | AI agents for B2B buying and selling | Product identity |
| `public.home.hero` | H1 | Put an agent on your next business purchase. | Supported buying mission exists |
| `public.home.body` | Supporting copy | SIRA helps your team define what it needs, compare options, and move a decision forward. SEIL helps sellers prepare product evidence and respond to buyers whose requirements they can meet. | Keep each verb within supported behavior |
| `public.home.buyer_cta` | Primary buyer CTA | Start a buying mission | Route to SIRA/auth with intent |
| `public.home.seller_cta` | Seller CTA | Prepare product evidence | Route to SEIL/auth with intent |
| `public.home.control_note` | Supporting line | Review the evidence. Choose what to share. Approve the actions that need your authority. | Release and approval controls work |
| `public.buyer.heading` | Buyer section H2 | Choose with your company's needs in view. | Company context usable |
| `public.buyer.body` | Buyer section | Bring the outcome, your current stack, and the requirements that matter. SIRA turns them into a brief and an evidence-backed comparison you can inspect and correct. | Actual brief/evidence flow |
| `public.buyer.benefit_1` | Benefit | Keep requirements and trade-offs in one place. | Persistent decision artifact |
| `public.buyer.benefit_2` | Benefit | See what supports each option and what is still unknown. | Source and uncertainty views |
| `public.buyer.benefit_3` | Benefit | Give reviewers the exact decision they need to make. | Supported review flow |
| `public.seller.heading` | Seller section H2 | Help the right buyers understand your product. | Qualified response available |
| `public.seller.body` | Seller section | Give SEIL your product's capabilities, sources, and limits. Prepare reviewed evidence that can answer relevant buyer questions without rebuilding the same response each time. | Reusable seller evidence flow |
| `public.seller.benefit_1` | Benefit | Connect product claims to their supporting sources. | Claim/source mapping |
| `public.seller.benefit_2` | Benefit | Make fit and limitations clear before a sales conversation. | Supported anti-fit and scope |
| `public.seller.benefit_3` | Benefit | Keep drafts private until an authorized publication. | Verified publication boundary |
| `public.how.heading` | How-it-works H2 | From a business need to a clear next step. | Supported sequence |
| `public.how.step_1` | Step | Define the outcome — build a brief around your needs and constraints. | Brief flow |
| `public.how.step_2` | Step | Inspect the options — review evidence, costs, effort, and unanswered questions. | Comparison scope |
| `public.how.step_3` | Step | Bring in the right people — request information, review, or an introduction when needed. | Only list available paths |
| `public.how.step_4` | Step | Review the next action — approve the exact supported terms or handoff. | Exact approval/handoff |
| `public.categories.heading` | Categories H2 | Start with the job you need done. | Outcome-first entry |
| `public.categories.body` | Category explanation | Explore tools and approaches for your team's work. Coverage, available evidence, and supported actions are shown for each category. | Actual capability coverage visible |
| `public.connections.heading` | Integrations H2 | Use relevant business context, with clear access. | Connected context only if implemented |
| `public.connections.manual` | Manual-first variant | Add company context directly. Connect supported services when you need their data. | Do not imply currently unavailable connections |
| `public.control.heading` | Control section H2 | Know what your agent can do next. | Actual delegation/status |
| `public.control.body` | Control section | See what has been checked, what needs your input, and what information will be shared before a consequential action. | Real work and release views |
| `public.proof.heading` | Product proof H2 | See the work behind a decision. | Show real/clearly labeled demonstration |
| `public.proof.caption` | Demo caption | Example workflow. Product names and terms are illustrative. | Use for synthetic demonstrations only |
| `public.close.heading` | Closing H2 | What does your team need to buy or change? | Buyer entry |
| `public.close.body` | Closing copy | Start with the outcome. Build the brief with SIRA, or prepare your product's evidence with SEIL. | Available entry paths |

Use a real product walkthrough or clearly labeled illustrative flow as proof before case studies exist. Publish customer logos, testimonials, comparison claims, time saved, or savings only with supporting evidence and applicable permission. Do not invent social proof to fill a layout.

### Navigation, metadata, and secondary pages

| ID / surface | Heading or title | Supporting text / controls |
| --- | --- | --- |
| `public.nav` | How it works · For buyers · For sellers · Pricing · Security | SIRA sign in · SEIL sign in; anchors or actual routes with meaningful focus/scroll behavior |
| `public.meta.home` | SIRA + SEIL — AI agents for B2B buying and selling | SIRA helps teams compare business tools and review decisions. SEIL helps sellers prepare product evidence and respond to relevant buyer needs. |
| `public.meta.pricing` | Pricing · SIRA + SEIL | Review available platform terms and understand how they relate to product costs. Publish only when the page provides that information accurately. |
| `public.pricing.heading` | Understand the costs before you commit. | Separate product pricing, estimated usage, and any applicable platform fee. |
| `public.pricing.terms` | Current commercial terms | Populate with approved actual terms, currency/tax basis, and conditions. If undecided, state “Pricing is being finalized” and provide only a verified inquiry path. |
| `public.pricing.rank` | How recommendations are made | Explain actual ranking inputs and commercial policy. Use “Payment does not affect fit ranking” only when the business policy and implementation support it. |
| `public.security.heading` | How access, evidence, and actions are controlled. | Explain buyer-private context, seller-private drafts, released projections, required authority, evidence provenance, and honest external outcomes in concrete terms. |
| `public.security.sections` | Company context · Product evidence · Sharing and consent · Commercial actions · Connections | Tie each section to verified implemented behavior; distinguish publisher attestation from independent verification. |
| `public.privacy.heading` | How information is used and shared. | Explain actual purposes, storage/retention, model/provider use, disclosures, rights/controls, and a working policy contact. Business/legal policy supplies the content. |
| `public.terms.heading` | Using SIRA and SEIL. | Current service scope, actor responsibilities, evidence limitations, commercial relationships, applicable terms, and contact. Do not generate obligations that have not been adopted. |
| `public.footer` | SIRA + SEIL | Product links, Pricing, Security, Privacy, Terms, supported contact/help destination; accurate copyright/operator identity. |

Privacy and terms headings are editorial drafts; policy text needs the appropriate business/legal source. This plan does not require repeated sign-off for routine copy edits or confer authority to publish new legal/commercial terms.

### FAQ draft

| Question | Draft answer |
| --- | --- |
| What does SIRA do? | SIRA helps a buying team turn a need into a brief, investigate options, and review a supported next step. What it can do depends on the category, evidence, access, and authority available. |
| What does SEIL do? | SEIL helps sellers prepare product claims with supporting sources, review what can be published, and respond to relevant buyer requirements. |
| Do I need to connect our company tools? | You can start with company context you provide directly. Supported connections can add specific data when you authorize access. |
| Will a seller see our budget? | Buyer-private information stays outside seller-facing views unless a specific permitted release includes it. Review the exact recipient and information before sharing. |
| Can an agent buy something without me? | Protected commercial actions follow the application's authority and approval rules. Review the exact scope shown for the action; selecting an option is different from authorizing a purchase. |
| Is every product claim independently verified? | No. The source and support for a claim matter. Public research, seller-published evidence, and independent attestations have different meanings, which the product should show. |
| Does opening a payment page complete the purchase? | No. It confirms only the supported handoff state. Purchase or activation needs its own confirmation. |
| Which categories and integrations work? | Show the actual current coverage and available actions here. Research coverage and connected or executable capabilities must be listed separately. |

## 3. Entry, company context, and mission copy

| ID / state | Heading / label | Body, helper, or action |
| --- | --- | --- |
| `auth.sira.heading` | Sign in to SIRA | Continue your company's buying work. |
| `auth.seil.heading` | Sign in to SEIL | Prepare product evidence and respond to relevant buyer needs. |
| `auth.google` | Continue with Google | Identity sign-in only; do not imply a suite connection. |
| `auth.email` | Continue with email | Fields: Email address · Password. Use actual supported auth methods. |
| `auth.guest` | Try a guest workspace | Available actions are limited. Show whether/how work can be preserved only after verifying that behavior. |
| `auth.returning` | Continue where you left off | Return to the permitted mission or artifact after sign-in. |
| `auth.step_up` | Verify your identity to continue | This action requires recent verification. Your review is still available. Action: Verify identity. |
| `auth.wrong_account` | This account cannot access this workspace | Sign in with an account that has access, or return to your workspace. |
| `auth.expired` | Your session has expired | Sign in again to continue. Describe draft preservation only if confirmed. |
| `company.heading` | What should SIRA know about your company? | Add the facts that matter for this decision. You can leave other details for later. |
| `company.fields` | Current tools · Team size or expected usage · Requirements · Policies · Decision owners | Each field explains its purpose and source; avoid a compulsory all-company survey. |
| `company.source.user` | Provided by your team | Add author/date where permitted. |
| `company.source.connected` | From {provider} · Last synced {date} | Separate last attempt from last successful sync. |
| `company.source.inferred` | Suggested assumption — confirm or change | An assumption is not a confirmed requirement. |
| `company.source.unknown` | Not confirmed | Provide the fact or continue without it when valid. |
| `company.change.heading` | Update this company fact | Explain what changed and why. Actions: Save new version · Cancel. |
| `company.change.impact` | This change may affect {count} active decisions | Review affected decisions. Render plural/singular accurately. |
| `company.conflict` | Two sources disagree | Review both values before choosing which applies. |
| `company.private` | Private to your buyer workspace | Use the correct party and actual visibility scope. |
| `mission.sira.heading` | What does your company need to buy or change? | Describe the outcome, current problem, or tool you are considering. |
| `mission.seil.heading` | What product or buyer question should we work on? | Prepare evidence, review a gap, or respond to a released buyer need. |
| `mission.input` | Describe the outcome | Placeholder supports the label; it does not replace it. Action: Start mission. |
| `mission.starter.buy` | Compare tools for our support workflow | Starter must produce a supported mission rather than canned success. |
| `mission.starter.review` | Review our current tool and alternatives | Research/preparation wording until renewal execution exists. |
| `mission.return.heading` | Continue your work | Show actual recent missions and unresolved tasks. |
| `mission.return.summary` | Since your last visit | Factual linked changes only; empty variant: No material changes since your last visit. |
| `mission.scope.heading` | What SIRA will do | Compare options against this brief and prepare a recommendation. Sharing information or taking a protected action follows the applicable review and authority rules. |
| `mission.work.heading` | What has been checked | Populate with recorded work; avoid fake progress percentages. |
| `mission.waiting` | Waiting for {owner_or_role} | {Specific dependency}. Action: Open the relevant artifact. |

### Brief and decision artifacts

| ID / surface | Heading / labels | Body or action |
| --- | --- | --- |
| `brief.heading` | Review your buying brief | Confirm the outcome and requirements before evaluating options. |
| `brief.fields` | Outcome · Must meet · Should meet · Nice to have · Current tools · Quantity or usage · Timing · Cost assumptions | Private ceiling/budget has explicit visibility; required fields match actual evaluation needs. |
| `brief.unknown` | Not sure yet | Explain what can proceed and which decision remains blocked. |
| `brief.save` | Save brief | Use Confirm brief only when that exact transition exists. |
| `brief.change.heading` | Review this requirement change | Show old/new requirement and affected evaluation. Actions: Apply change and re-evaluate · Keep current requirement, when supported. |
| `brief.policy_note` | Applies to this mission | Offer a separate authorized path for company-policy changes. |
| `research.heading` | Finding options for your brief | Show current verified operation/coverage. |
| `research.partial` | Research is incomplete | You can inspect the available findings. {Specific missing work} still needs attention. |
| `research.none` | No candidates found in this search | Review the search scope or add evidence. Do not imply no suitable product exists anywhere. |
| `comparison.heading` | Compare your options | Review requirements, total commitment, effort, and trade-offs. |
| `comparison.columns` | Requirement · Evidence · Estimated cost · Commitment · Adoption effort · Trade-off · Next step | Adapt the comparison orientation to the task. |
| `comparison.recommendation` | Recommended next step | Include supporting reason, main trade-off, and unresolved condition. |
| `comparison.unknown` | Needs evidence | This requirement has not been established for this edition and scope. |
| `comparison.conflict` | Conflicting evidence | The available sources disagree. Review them before relying on this claim. |
| `comparison.blocked` | Does not meet a required condition | Name the condition and actual supporting evidence. |
| `comparison.no_fit` | No eligible option is ready to recommend | Explain which requirements block progress and which facts remain unknown. |
| `comparison.actions` | Keep for comparison · Need evidence · Ask the seller · Review plan · Keep current tools · Defer decision | Render only supported actions and preserve actual semantics. |
| `comparison.cost_note` | Estimate based on {usage_or_quantity} over {horizon} | Show original units, commitment, known fees, unknown charges, and currency basis. |
| `comparison.annual_note` | Annual commitment | {Total} committed for {period}. {Monthly_equivalent} is an equivalent, not a monthly cancellation option. |
| `comparison.current_version` | Current decision · Version {version} | Historical variant: Historical version — open the current decision to act. |
| `evidence.heading` | What supports this requirement? | Show exact claim/scope, source class, date, currentness, and source detail. |
| `evidence.origin.public` | Public research | Source-linked observations; not seller-attested by default. |
| `evidence.origin.seller` | Seller-published evidence | Identify source and publisher scope; do not imply independent verification. |
| `evidence.stale` | Evidence needs a refresh | Last observed {date}. Explain what action/evaluation is limited. |
| `evidence.actions` | Open source · Review history · Request evidence | Source access/research capability governs availability. |

## 4. Seller, review, qualification, and consent copy

| ID / state | Heading / label | Body or action |
| --- | --- | --- |
| `seller.products.heading` | Your products | Add a product or continue preparing evidence. |
| `seller.add` | Add product | Fields: Product name · Official website · Edition · Category; current contract determines required fields. |
| `seller.draft.heading` | Prepare product evidence | Connect each important claim to its supporting source. |
| `seller.draft.private` | Private draft | Only a reviewed, authorized publication makes the permitted content available to buyers. |
| `seller.claims` | Claims and sources | Show unsupported, conflicting, supported, and stale claims separately. |
| `seller.upload` | Add a source | Show actual accepted formats and size limits. Do not advertise PDF/Office ingestion unless implemented. |
| `seller.fit` | Where this product fits | Include requirements and supported scope. |
| `seller.anti_fit` | Where this product is not a fit | Help buyers avoid an unsuitable option. |
| `seller.gaps` | Resolve these evidence gaps | Each gap links to the claim/source needing work. |
| `seller.review.heading` | Review changes to version {version} | Show changed claims, sources, fit rules, and proposed publication. |
| `seller.review.submit` | Send this revision for review | Use current revision and reviewer routing. |
| `seller.review.waiting` | Waiting for review | {Reviewer_or_role} needs to review this revision. |
| `seller.review.changed` | This draft changed during review | Review the current revision before approving publication. |
| `seller.review.request_changes` | Request changes | Describe the specific claim or source that needs work. |
| `seller.publish.heading` | Review what buyers will see | Show the exact buyer-safe projection. |
| `seller.publish.action` | Publish evidence v{version} | Add recipient/scope context; publication must have current required review. |
| `seller.publish.success` | Evidence v{version} published | State the persisted publication and effective scope. |
| `seller.publish.failure` | This revision was not published | Explain known state; describe preservation of the previous publication only if confirmed. |
| `qualification.heading` | Does your product meet this buyer's needs? | You are reviewing the requirements released to your workspace. |
| `qualification.actions` | Fits these requirements · Not a fit · Need more information | Map to actual response commands. |
| `qualification.fit_helper` | Add supporting evidence and any conditions | Avoid an unsupported blanket fit assertion. |
| `qualification.anti_fit_helper` | Explain the requirement your product cannot meet | Declining a poor fit is a valid result. |
| `qualification.info_helper` | What information would change your answer? | Ask for the minimum relevant clarification. |
| `release.heading` | Review this information before sharing | Recipient: {recipient}. Purpose: {purpose}. Show exact fields and current version. |
| `release.private_note` | Not included in this release | List meaningful excluded private fields from trusted release metadata, without revealing prohibited values. |
| `release.action` | Share this brief | Name a different object when sharing something else. |
| `release.result` | Brief shared with {recipient} | Show authoritative release time/version and inspectable receipt. |
| `consent.heading` | Review this introduction | Show parties, exact contact information to release, purpose, scope, expiry. |
| `consent.action` | Agree to this introduction | Separate from buying, publishing, or granting access. |
| `consent.decline` | Decline introduction | Only when the supported consent workflow provides that action. |
| `consent.waiting` | Waiting for the other party's consent | Do not expose private contact details or unsupported internal reasons. |
| `consent.complete` | Introduction recorded | State the supported delivered/recorded effect precisely and show next owner. |
| `consent.expired` | This introduction needs current consent | Review the current scope before continuing. |

## 5. Human attention, terms, approval, and outcome copy

| ID / state | Heading / label | Body or action |
| --- | --- | --- |
| `inbox.heading` | Your next actions | Groups: Needs you · Waiting on others · Updates. |
| `inbox.empty` | Nothing needs your attention right now | Start a mission or return to existing work. |
| `inbox.question` | Confirm {decision_relevant_fact} | Explain why the answer affects the next step. |
| `inbox.blocked` | {Work_item} is waiting on {dependency} | Next owner: {owner_or_role}. Use supported direct link. |
| `inbox.credential` | Authorize this connection | Review access in the secure connection flow. Do not paste credentials into chat. |
| `offer.heading` | Review the exact terms | Product/edition · Quantity · Unit price · Total · Currency · Commitment · Conditions · Expires · Recipient. |
| `offer.propose` | Send this offer | Bound to the current supported buyer-owned proposal. |
| `offer.counter` | Review the seller's counteroffer | Show exact changed terms and current expiration. |
| `offer.accept` | Accept these terms | Clarify that acceptance is followed by any required approval. |
| `offer.agreed` | Terms agreed — approval still required | Use only when that is the authoritative current state. |
| `offer.changed` | The offer changed while you were reviewing | Your approval was not applied. Review version {version}. Use the latter sentence only when the no-effect result is confirmed. |
| `approval.heading` | Review this action before approving | Show exact object/version, consequence, recipient/target, cost/access scope, conditions, expiry. |
| `approval.purchase` | Approve these purchase terms | Object and total remain visible near the control. |
| `approval.release` | Approve this release | Use separate exact content/recipient review. |
| `approval.no_authority` | An authorized reviewer needs to approve this | Required role: {role}. Provide only supported assignment/request/verification actions. |
| `approval.pending` | Approval requested | Show current required reviewers, completed reviews, and unresolved conditions. |
| `approval.complete` | These terms are approved | Approval applies to {object} version {version} until {expiry}, subject to its actual conditions. |
| `approval.expired` | This approval has expired | Review the current terms and request approval again. |
| `approval.superseded` | A newer version needs review | Historical approval does not authorize changed terms. |
| `handoff.heading` | Continue to the external payment page | Recipient · Amount · Destination · Reference · Expires; approved version remains inspectable. |
| `handoff.prepare` | Prepare payment handoff | Only after required current approval. |
| `handoff.open` | Open {recipient} payment page | Opening the page does not confirm that payment was made. |
| `handoff.opened` | Payment page opened | Complete the next step with {recipient}. We have not confirmed payment. |
| `handoff.unknown` | We could not confirm whether the page opened | Check the recorded handoff status before trying again. |
| `handoff.expired` | This handoff has expired | Review the current terms and prepare a supported new handoff. |
| `outcome.heading` | What happened after the handoff? | Record only supported outcomes and source/owner. |
| `outcome.self_reported` | Reported by {actor} on {date} | Separate from provider-confirmed result. |
| `outcome.unconfirmed` | Purchase outcome not confirmed | Next owner: {owner_or_role}. Show the supported verification or external task. |

Avoid generic approval checkboxes or repeated confirmation for ordinary reads. The explicit action plus the exact review surface should carry the meaningful decision. Additional verification follows actual server policy and consequence.

## 6. Connection, category, settings, and lifecycle copy

| ID / state | Heading / label | Body or action |
| --- | --- | --- |
| `connection.heading` | Company connections | See which data and actions are available to your workspace. |
| `connection.value` | Use {provider} for {specific_use_case} | State the actual resources needed and business value. |
| `connection.signin_note` | Sign-in and business-data access are separate | Signing in with this provider does not connect your company's data. |
| `connection.scope` | Review the access requested | Provider/account, exact data/actions, purpose, consenting role, retention/disconnect behavior. |
| `connection.authorize` | Authorize {provider} access | Only when the real provider flow is available. |
| `connection.admin` | An administrator needs to authorize this access | Show supported admin handoff or return path; don't request credentials in chat. |
| `connection.connected` | Connected to {account} | Show granted scope; sync status and usable actions separately. |
| `connection.usable` | {Capability} is available | Verified capability and last successful retrieval where relevant. |
| `connection.partial` | Some requested data is unavailable | Explain missing scope/resource and affected actions. |
| `connection.syncing` | Syncing permitted data | Do not promise unbounded company awareness. |
| `connection.stale` | Last successful sync: {date} | Current attempts/errors remain distinct. |
| `connection.expired` | Access needs to be renewed | Action: Review access and reconnect. |
| `connection.revoked` | Access was revoked | Dependent actions are unavailable. Preserve/manual context behavior follows policy. |
| `connection.disconnect` | Disconnect {provider} | Explain future access, provider revocation, and retained information before confirming. |
| `connection.unavailable` | This connection is not available yet | Show manual alternative or supported setup; no working-looking Connect button. |
| `category.api` | Compare cost at your expected usage | Inputs: Billing meter · Expected usage · Peak/high usage · Included limits · Overage. |
| `category.mcp` | Review what this tool can access and change | Publisher · Version · Host compatibility · Data access · Read/write scope · Revocation. |
| `category.skill` | Review this skill and its dependencies | Intended task · Source/version · Required tools · Execution scope · Update policy. |
| `category.internal` | Compare building and buying | Existing systems · Implementation effort · Maintenance owner · Access · Exit effort. |
| `category.suite` | Compare the suite and the change it requires | Seats/storage · Current identity/email · Overlap · Admin owner · Migration effort. |
| `category.research_only` | Research and preparation only | This path does not currently purchase, install, migrate, or deploy on your behalf. Use only the relevant unsupported verbs. |
| `lifecycle.heading` | Review what has changed | Compare current facts and requirements with the previous decision. |
| `lifecycle.renewal` | Prepare a renewal decision | Confirm actual terms, notice date, usage, alternatives, and owner. |
| `lifecycle.migration` | Prepare the transition plan | Purchase, access grants, data migration, and production cutover require their own supported steps. |
| `settings.heading` | Company settings | Sections: Profile and identity · Context · Policies and access · Connections · Notifications · Privacy and sharing, limited to supported functions. |
| `settings.notification` | Where should action requests appear? | In-app · Verified additional channels; show saved preference separately from channel availability. |
| `settings.quiet_hours` | Quiet hours | Start · End · Time zone; explain actual delivery behavior and exceptions if any. |
| `settings.disclosure` | Default sharing preferences | A preference does not replace the required exact release/consent for an action. |

## 7. Shared errors, assistance, and follow-up

### Error and status copy patterns

| ID / condition | Draft text | Required action/announcement |
| --- | --- | --- |
| `error.validation` | Check the highlighted fields. | Link summary to fields; specific inline reason; preserve input. |
| `error.network.read` | We could not load {artifact}. | Retry read · Return to work; do not call it empty. |
| `error.provider` | Research is unavailable right now. | Preserve completed work and offer supported retry; no canned success. |
| `error.conflict` | This item changed in another session. | Review the current version before applying your change. |
| `error.denied` | You do not have access to this action. | Name required role where policy permits; supported owner/verification route. |
| `error.unknown_result` | We could not confirm the result. | Check status before trying again. Reconcile rather than create a new effect. |
| `error.not_found` | This item is unavailable or you do not have access. | Avoid revealing another tenant's object existence; safe workspace route. |
| `error.page` | This page could not be loaded. | Try again · Return to your workspace; preserve supported context. |
| `error.not_found_page` | We could not find that page. | Check the link or return to your workspace. |
| `status.saved` | Saved. | Announce without moving focus unnecessarily; include object if ambiguity matters. |
| `status.running` | {Actual operation} is in progress. | Don't announce every streamed token; provide a useful completion/status change. |
| `status.disabled` | {Action} is unavailable because {specific_reason}. | Explain near the control or in a focusable associated message. |

### Agent response structures

**Result:** “I found {supported_result}. The main trade-off is {trade_off}. {Unresolved_condition}. Review {artifact_link} to choose the next step.” Use only facts supported by accessible artifacts; omitted facts need no invented filler.

**Clarification:** “{Specific fact} changes {decision consequence}. Which applies: {supported choices}?” Offer unknown/defer when valid. Do not make the user answer an entire questionnaire in the conversation.

**Proposed change:** “I suggest changing {criterion} from {old} to {new} because {reason}. This has not been applied.” Add a supported review action; do not report it as saved.

**Waiting:** “The next step is waiting for {role_or_dependency}. {Specific action} is needed to continue.” Reveal only permitted owner/dependency information.

**Failure:** “{Work} could not be completed. {Known persisted result}. {Supported recovery}.” If the result is unknown, say so and reconcile it.

### Notification and follow-up templates

Only render/send through an implemented, authorized delivery channel. These are template drafts, not instructions to send messages.

| ID | Subject/title | Body and destination |
| --- | --- | --- |
| `notification.action` | Review needed: {mission_title} | {Specific work} needs your review. Open the current artifact to see the scope and next action. CTA: Review request. |
| `notification.evidence` | Evidence request: {product_name} | A released requirement needs additional support. Open the permitted question in your seller workspace. |
| `notification.changed` | Terms changed: {mission_title} | A newer offer needs review. Open the current version before acting. |
| `notification.waiting` | Update on {mission_title} | {Permitted material change}. CTA: Open work. Avoid sending routine “thinking” events. |
| `notification.outcome` | Follow up on {mission_title} | Has the decision produced the outcome your team needed? Record a supported update when convenient. |

Exclude private budgets, seller floors, credentials, sensitive terms, contacts, or evidence excerpts from general notifications. Deep links revalidate access and current state on open. Respect actual preferences, consent, quiet-hours behavior, and delivery limits.

## 8. Copy completion checklist

- [ ] Every public route and product flow has an intentional heading and primary action.
- [ ] Every control has a visible or accessible name; helper text explains decision-relevant inputs.
- [ ] Empty, loading, partial, blocked, stale, conflict, error, uncertain, and confirmed states have specific text.
- [ ] Marketing promises map to current verified capabilities; synthetic proof stays labeled.
- [ ] Pricing, ranking policy, privacy, terms, security, and integration claims have appropriate factual/policy support.
- [ ] Dynamic amounts, dates, units, versions, counts, and recipients use trusted data and correct formatting.
- [ ] Consent, agreement, approval, execution, handoff, and outcome language remain distinct.
- [ ] Agent explanations distinguish facts, assumptions, proposed changes, and applied changes.
- [ ] Notifications and support destinations actually work before being advertised.
- [ ] Text is checked in real wide/narrow layouts, with long values, high zoom, keyboard, and assistive technology.
- [ ] Representative users can identify the audience, task, main trade-off, action consequence, and next owner.

Complete this catalog during steps 02–13 as new states are found. A missing state is a flow-design issue as well as a copy gap; add it to the relevant implementation task.

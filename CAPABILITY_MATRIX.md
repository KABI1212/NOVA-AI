# NOVA AI Capability Matrix

This maps the current codebase against the broader advanced AI capability list.

Status legend:

- `implemented`: available in the product now
- `partial`: present in some form, but not fully productized
- `missing`: not implemented yet in the current app

## Current Coverage

| Capability Group | List Items | Status | Current Coverage | Main Gaps |
| --- | --- | --- | --- | --- |
| Core AI capabilities | 1-5 | implemented | Multi-turn chat, instruction following, context-aware conversations, role-style prompting, multi-provider answers | No formal system-prompt management UI |
| Tool and action systems | 6-10 | partial | Provider routing, search/document/image helper flows, prompt-driven assistant modes | No formal function-calling registry, no code sandbox, no agent orchestration framework |
| Structured data handling | 11-15 | partial | API responses are structured at the route layer, markdown formatting is controlled | No schema-enforced JSON output mode across product workflows |
| Memory and context | 16-20 | partial | Chat history, conversation summaries, session-based context, stored conversations | No durable long-term personal memory or per-user profile memory engine |
| Retrieval and knowledge | 21-25 | partial | Document Q&A, lexical retrieval, optional embedding-assisted retrieval, search mode | No managed knowledge-base admin workflow or persistent external vector store |
| Embeddings and semantic search | 26-30 | partial | OpenAI embeddings, similarity search for documents, lexical fallback | No clustering, recommendations, or duplicate-detection product surfaces |
| Audio and voice | 31-35 | partial | Speech transcription and TTS endpoints exist | No full real-time duplex voice assistant pipeline or broad multilingual voice UX |
| Vision and image understanding | 36-40 | partial | Image upload/remix flows and screenshot/image-aware prompts exist | No dedicated OCR pipeline, object detection, or formal vision QA workflow |
| Image generation | 41-45 | implemented | Text-to-image, prompt optimization, image remix/edit flows | Could be expanded with stronger design templates and editing controls |
| Multi-model and multi-AI | 46-50 | implemented | Provider fallback, routing, hybrid provider logic, evaluator chains | No cost-aware routing policy engine yet |
| Real-time and streaming | 51-55 | implemented | Token streaming, live chat UX, event-style streamed responses | No unified real-time event bus or WebSocket assistant channel |
| Authentication and security | 56-60 | partial | JWT auth, rate limiting, new email OTP login flow | No RBAC, moderation integration, or abuse-detection workflow yet |
| Customization | 61-65 | partial | Prompt shaping, provider/model selection, response style tuning | No fine-tuning pipeline or admin-controlled behavior profiles |
| Integrations | 66-70 | partial | MongoDB, Redis, provider APIs, web search integrations | No CRM/ERP/cloud connector layer or automation marketplace |
| Advanced reasoning | 71-75 | implemented | Multi-step reasoning, code/debug/explain flows, evaluator chains | Could add explicit planner/executor separation for harder tasks |
| Code and dev features | 76-80 | implemented | Code generation, explanation, debugging, optimization | No PR review automation or repo connector workflow in the product |
| Data analysis | 81-85 | partial | Summaries and report-style answers exist | No dedicated CSV/Excel analysis pipeline or chart generation |
| Multilingual support | 86-90 | partial | General-model translation and tone adjustment are possible | No explicit localization workflows or language-aware routing |
| Interactive systems | 91-95 | implemented | Chatbot, learning assistant, image assistant, reasoning assistant | No game/NPC-specific runtime systems |
| Enterprise features | 96-100 | partial | Logging, rate limiting, deployable FastAPI/React stack | No cost dashboards, SLA telemetry, or production monitoring suite |
| Bleeding edge | 101-105 | missing | None productized beyond light orchestration helpers | No autonomous agents, self-improving workflows, or IoT action systems |

## Implemented In This Pass

- Item `56`: email OTP verification workflow for login
- Supporting mail delivery via SMTP or SendGrid-compatible configuration
- Frontend OTP verification step integrated into the existing login screen

## Highest-Value Next Additions

1. Structured tool calling
   Add a server-side tool registry with schema-validated JSON responses for chat actions and external integrations.

2. Retrieval hardening
   Add persistent vector storage, OCR ingestion, and knowledge-base management for documents and screenshots.

3. Security and governance
   Add moderation, resend throttling, audit logs, and role-based access control.

4. Operations
   Add provider cost tracking, latency metrics, and health dashboards.

5. Real-time voice
   Add streaming speech input/output and interruption-aware voice sessions.

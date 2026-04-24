# NOVA AI .env API Keys Fix - TODO

## Plan Steps
- [x] 1. Confirm all provider files checked for hardcoded env names
- [x] 2. Edit backend/services/ai_service.py: Replace hardcoded getattr() with standard settings.XXX_API_KEY
- [x] 3. Edit affected providers/*.py (openai_provider.py + others if needed)
- [ ] 4. Restart backend server
- [ ] 5. Test /api/status or providers endpoint
- [ ] 6. Verify frontend warning gone
- [ ] 7. Update TODO.md to ✅ COMPLETE

**Status: Starting edits...**


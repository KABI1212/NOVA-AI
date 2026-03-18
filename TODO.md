# NOVA AI Logo & Font Update - TODO

## Plan Implementation Steps (Approved)

### 1. [x] Create TODO.md 
### 2. [x] Update tmp/nova-ai.html
   - Replace logo SVG with sparkle/star icon SVG matching "old Nova AI" style (blue sparkle + blue text)
   - Replace ALL font-family declarations: 'DM Sans'/'Syne' → 'Times New Roman', Times, serif
   - Remove Google Fonts link
### 3. [x] Verify React frontend (Layout.jsx & index.css)
   - Confirmed Times New Roman already applied globally in index.css
   - Confirmed Layout.jsx uses Sparkles icon (sparkle) + blue text "NOVA AI" intact
### 4. [ ] Test standalone app
   - Open tmp/nova-ai.html in browser
   - Verify logo change & Times New Roman everywhere
### 5. [ ] Test React app
   - cd frontend && npm run dev
   - Verify no font/logo regressions
### 6. [ ] Update TODO.md with completion status
### 7. [ ] Attempt completion

**Next Step**: Update `tmp/nova-ai.html`


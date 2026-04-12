# Render + Vercel Deployment

This project is set up to deploy with:

- Backend: Render web service
- Frontend: Vercel
- Database: MongoDB Atlas
- Cache / rate limiting: Redis

## 1. MongoDB Atlas

Create a MongoDB Atlas cluster and copy the connection string.

Recommended database name:

```env
nova_ai
```

Use the Atlas connection string as `DATABASE_URL` on Render, for example:

```env
mongodb+srv://USERNAME:PASSWORD@CLUSTER_URL/nova_ai?retryWrites=true&w=majority
```

## 2. Render Backend

This repo includes `render.yaml` for the backend and a Render key-value instance.

### Render service settings

- Runtime: Docker
- Docker context: `./backend`
- Dockerfile: `./backend/Dockerfile`
- Health check path: `/health`
- Disk mount path: `/app/uploads`

### Required backend environment variables

Set these on Render:

```env
DATABASE_URL=mongodb+srv://USERNAME:PASSWORD@CLUSTER_URL/nova_ai?retryWrites=true&w=majority
MONGODB_REQUIRED=true
CORS_ORIGINS=https://your-frontend.vercel.app
FRONTEND_URL=https://your-frontend.vercel.app
SECRET_KEY=generate-a-long-random-secret
REDIS_URL=<attach from Render key value service>
UPLOAD_DIR=/app/uploads
DEBUG=false
AI_PROVIDER=auto
AUTH_ALLOW_PASSWORD_ONLY_FALLBACK=true
```

The backend also accepts Vercel and Render deployment origins by default through
`CORS_ORIGIN_REGEX`, which helps preview deployments and standard `.vercel.app` /
`.onrender.com` frontends work without a browser CORS failure. You should still
set `CORS_ORIGINS` to your main production frontend URL explicitly. Set
`FRONTEND_URL` to the same deployed frontend URL so provider headers such as
OpenRouter use the correct public origin instead of a localhost fallback.

Add whichever provider keys you want to use:

```env
GOOGLE_API_KEY=
GEMINI_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEEPSEEK_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
```

### Email OTP (Required For Real Verification Emails)

If you want signup/login/reset OTP in real inboxes, configure SMTP on Render:

```env
EMAIL_PROVIDER=smtp
EMAIL_FROM=yourgmail@gmail.com
EMAIL_FROM_NAME=NOVA AI
EMAIL_REPLY_TO=yourgmail@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=yourgmail@gmail.com
SMTP_PASS=your-16-char-google-app-password
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT_SECONDS=10
```

Legacy aliases still supported: `EMAIL_FROM_ADDRESS`, `SMTP_USERNAME`, `SMTP_PASSWORD`.

Important:

- Keep `DEBUG=false` on Render.
- If SMTP is still being set up, `AUTH_ALLOW_PASSWORD_ONLY_FALLBACK=true` lets signup and login continue without waiting on email OTP delivery.
- After adding/updating env vars, redeploy backend: Render -> Manual Deploy -> Deploy latest commit.
- Verify status at `https://your-render-backend.onrender.com/api/status` and confirm:
  - `capabilities.auth.email.ready` is `true`
  - `capabilities.auth.email.delivery_mode` is `email`

## 3. Vercel Frontend

Deploy the `frontend` directory as the Vercel project root.

This repo includes `frontend/vercel.json` so React Router routes resolve to `index.html`.

### Required frontend environment variable

```env
VITE_API_URL=https://your-render-backend.onrender.com
```

After setting it, redeploy the frontend.

## 4. Domain Wiring

Use the deployed Vercel URL in Render:

```env
CORS_ORIGINS=https://your-frontend.vercel.app
```

If you later add a custom domain, include both domains:

```env
CORS_ORIGINS=https://your-frontend.vercel.app,https://app.yourdomain.com
```

## 5. Important Notes

- Document uploads are stored on disk, so the Render backend should keep the attached disk.
- Without a persistent disk, uploaded documents can disappear after restarts or redeploys.
- Redis is used mainly for rate limiting. The app can fall back to in-memory limits, but production is better with Redis enabled.

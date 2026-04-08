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
SECRET_KEY=generate-a-long-random-secret
REDIS_URL=<attach from Render key value service>
UPLOAD_DIR=/app/uploads
DEBUG=false
AI_PROVIDER=auto
```

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

If you use email login OTP in production, also set SMTP or SendGrid variables.

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

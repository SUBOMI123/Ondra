FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build
# Not root: the node image's own user. It owns only .next (Next.js writes its cache there); the code stays read-only.
RUN chown -R node:node /app/.next
USER node
EXPOSE 3001
CMD ["npm", "start", "--", "--port", "3001", "--hostname", "0.0.0.0"]

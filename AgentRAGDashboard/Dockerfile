# =========================
# Stage 1 : Build Angular
# =========================
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./

RUN npm ci

COPY . .

RUN npm run build


# =========================
# Stage 2 : Nginx
# =========================
FROM nginx:alpine

COPY --from=build /app/dist/agent-ragdashboard/browser /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

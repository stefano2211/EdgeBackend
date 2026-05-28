# Etapa 1: Construcción
FROM node:20-alpine as build-stage

# Establecer directorio de trabajo
WORKDIR /app

# Copiar package.json y package-lock.json
COPY package*.json ./

# Instalar todas las dependencias
RUN npm ci

# Copiar el resto del código fuente
COPY . .

# Construir la aplicación para producción
RUN npm run build-only

# Etapa 2: Servidor de Producción (Nginx)
FROM nginx:stable-alpine as production-stage

# Copiar los archivos compilados desde la etapa de construcción al directorio de Nginx
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Copiar configuración personalizada de nginx para manejar el ruteo de Vue Router (Single Page Application)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Exponer puerto 80
EXPOSE 80

# Comando por defecto para arrancar nginx
CMD ["nginx", "-g", "daemon off;"]

FROM node:20-alpine

WORKDIR /uis

COPY website/package*.json ./website/
COPY backoffice/package*.json ./backoffice/

RUN cd website && npm install
RUN cd backoffice && npm install

COPY . .

RUN chmod +x ./start.sh

EXPOSE 3000 3001

CMD ["./start.sh"]
FROM node:latest

WORKDIR /usr/app

COPY package.json .
RUN npm install

COPY ./src .

EXPOSE 47170

CMD ["node", "./mqtt-lock.js"]
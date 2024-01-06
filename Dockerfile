FROM node:latest

WORKDIR /usr/app

COPY package.json .
RUN npm install

COPY ./apple-home-key-reader .

EXPOSE 47169

CMD ["node", "./lock.js"]
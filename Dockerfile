FROM node:latest

WORKDIR /usr/app

COPY package.json .
RUN npm install

COPY ./hap .

EXPOSE 47170

CMD ["node", "./lock.js"]
const express = require("express");
const axios = require("axios");
const https = require("https");
const fs = require("fs");
require("dotenv").config();

const app = express();
app.get("/api/v1/endpoints", (_req, res) => {
  console.log("Mirror engaged: ", process.env.PBENCH_SERVER);
  axios
    .get(`${process.env.PBENCH_SERVER}/api/v1/endpoints`, {
      headers: { Accept: "application/json" },
      httpsAgent: new https.Agent({
        ca: fs.readFileSync(
          "../server/pbenchinacan/etc/pki/tls/certs/pbench_CA.crt"
          )
      }),
    })
    .then((endpoints) => {
      res.setHeader("Content-Type", "application/json");
      res.send(endpoints.data);
    })
    .catch((err) => {
      console.log("Error: ", err.message);
    });
});

app.listen(3001, () => console.log("Mirror server running on localhost:3001"));

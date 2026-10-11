const websocket = require('isomorphic-ws');
const { createWebSocketStream } = require('./stream.js');
const mqttConn = require('mqtt-connection');
const { getIdToken, nanoid } = require('utils/util');
const { authorizer } = require('api');
const { version } = require('../version.json');
const lz4 = require('lz4-napi');
// AWS IOT does not allow -'s in clientId - 21-character ids are reserved for
// devices

const decoder = new TextDecoder();
const decompress = payload => lz4.decompressFrameSync(payload);

const stateTimeout = 5; // seconds
const timeoutQuantum = 100; // milliseconds
const qps = 1000 / timeoutQuantum; // quantums per second
const current = {};
let seq = 0;

// As an example, to reboot a device, send the following payload to its Site ID +
// "Managed ID" (mid):
// mqttClient.publish({
//   topic: `site/${siteid}/${mid}`,
//   payload: '^' + JSON.stringify({ reboot: true, viewer: mqttClient.clientId }),
// }

class MqttClient {
  async _disconnect() {
    console.log('url', this.mqttid, this.url);
    this.close({ reconnect: true });
  }

  _reconnect() {
    if (!this.url) return;

    if (this.reconnect) clearTimeout(this.reconnect);

    this.reconnectInterval = MqttClient.nextInterval(this.reconnectInterval);
    console.error(
      'mqtt reconnect',
      this.cfg?.siteid,
      this.ws ? this.ws.readyState : -1,
      this.reconnectInterval
    );
    this.reconnect = setTimeout(() => {
      this._connect(true);
    }, this.reconnectInterval);
  }

  static nextInterval(interval) {
    if (interval < 1000) return 1000;
    else return 3000;
  }

  async _disconnected() {
    console.log('mqtt disconnected');

    if (this.conn) {
      this.conn.destroy();
      delete this.conn;
    }

    if (this.cfg.onDisconnect) this.cfg.onDisconnect();

    this._reconnect();
  }

  async _kick() {
    this.kickInterval = MqttClient.nextInterval(this.kickInterval);
    if (!this.url) {
      clearInterval(this.interval);
      delete this.interval;
      return;
    }
    if (this.url && !this.ws) {
      console.log('KICKCON');
      this._connect();
    }
  }

  async _ping() {
    if (!this.url || !this.conn) return;

    this.conn.pingreq();
  }

  async _connect(fromTimer) {
    const token = await getIdToken({ logout: this.cfg?.logout });
    const ts = new Date().getTime();
    this.url = `wss://${this.cfg?.ep}/mqtt?x-amz-customauthorizer-name=${authorizer}&token=${token}&site=${this.cfg?.siteid}&fe=web&version=${version}&ts=${ts}&seq=${seq}`;
    seq++;

    if (fromTimer) this.reconnectInterval = MqttClient.nextInterval(this.reconnectInterval);

    if (this.interval) clearInterval(this.interval);

    this.interval = setInterval(() => this._kick(), this.kickInterval);
    if (this.reconnect) {
      clearTimeout(this.reconnect);
      delete this.reconnect;
    }
    let ws;
    try {
      ws = this.ws = window._mqttWs = new websocket(this.url, ['mqttv3.1']);
    } catch (e) {
      console.error('ws failed', e);
      throw e;
    }
    window._mqtt = this;
    window._mqttid = this.clientId;
    ws.on = ws.addEventListener;
    ws.once = (...args) => {
      ws.addEventListener(...args, { once: true });
    };
    ws.terminate = async () => {
      setTimeout(() => ws.close(), 500); // throws uncatchable exceptions so it doesn't deserve to be on normal stack
    };

    try {
      await new Promise((resolve, reject) => {
        let timeout = stateTimeout * qps;
        ws.addEventListener('close', () => this._disconnected());
        ws.addEventListener('open', () => {
          console.log(
            'ws connected in',
            (stateTimeout - timeout / qps).toFixed(1),
            'sec',
            this.cfg?.siteid
          );
          resolve();
        });
        // Sometimes iOS takes VERY long to connect (like 20+ seconds), so
        // restart the connection periodically if that happens.
        const check = () => {
          if (timeout <= 0 || ws.readyState > 1 || !this.url) {
            if (this.url) console.log('ws connection timed out!');

            return reject();
          }
          if (ws.readyState === 1) return resolve();

          timeout--;
          this.timeout = setTimeout(check, timeoutQuantum);
        };
        this.timeout = setTimeout(check, timeoutQuantum);
      });
      clearTimeout(this.timeout);
    } catch (e) {
      this._reconnect();
      return;
    }

    const conn = (this.conn = mqttConn(createWebSocketStream(ws)));

    try {
      await new Promise((resolve, reject) => {
        let timeout = stateTimeout * qps;
        conn.on('connack', () => {
          console.log('mqtt connected in', (stateTimeout - timeout / qps).toFixed(1), 'sec');
          resolve();
        });
        conn.connect({
          protocolVersion: 4,
          clientId: this.clientId, // can't have @, -, etc
          username: 'unilever',
          keepalive: 60,
        });
        conn.on('error', err => {
          console.error('ws error', err);
          this._disconnect();
          reject(err);
        });
        const check = () => {
          if (timeout <= 0 || ws.readyState > 1 || !this.url) {
            if (this.url) console.log('mqtt connection timed out!');

            return reject();
          }
          timeout--;
          this.timeout = setTimeout(() => check(), timeoutQuantum);
        };
        this.timeout = setTimeout(() => check(), timeoutQuantum);
      });
    } catch (e) {
      return this._reconnect();
    }
    clearTimeout(this.timeout);

    conn.on('disconnect', () => this._disconnect());
    conn.on('close', () => this._disconnect());

    conn.on('publish', pkt => {
      if (!this.url)
        // already closed
        return;

      try {
        let decode = true;

        switch (pkt.payload[0]) {
          case 36 /* $ */:
            pkt.payload = pkt.payload.subarray(1, pkt.payload.length);
            try {
              pkt.payload = decoder.decode(decompress(pkt.payload));
            } catch (e) {
              console.log('failed', e);
            }
            break;
          case 37 /* %BlockId,Chunk,NChunks%... chunked */: {
            // some mqtt brokers have a max message size, so we need to chunk it up
            let mdEnd = pkt.payload.indexOf('%', 1);
            if (mdEnd < 0) break;
            const [blockid, chunkid, _chunks] = pkt.payload
              .subarray(1, mdEnd)
              .toString()
              .split(',');
            const chunks = parseInt(_chunks);
            const blockKey = `${pkt.topic}%${blockid}`;
            const blockObj = (this.blocks[blockKey] ??= {
              nchunks: 0,
              chunks: new Map(),
              ts: Date.now(),
            });

            try {
              const payload = pkt.payload.subarray(mdEnd + 1);
              blockObj.chunks.set(
                chunkid,
                decoder.decode(decompress(payload)).toString()
              );
            } catch (e) {
              console.log('decomp failed', e);
            }

            if (blockObj.chunks.size === chunks) {
              let payload = '';
              for (let _i = 0; _i < chunks; _i++) {
                const i = `${_i}`; //.padStart(2, '0');
                payload += blockObj.chunks.get(i);
              }
              pkt.payload = payload;
              delete this.blocks[blockKey];
            } else {
              return;
            }
            break;
          }
          case 3: // RSH_DATA
          case 4: // RSH_CLOSE
            decode = false;
            break;
          default:
            pkt.payload = pkt.payload.toString();
            break;
        }

        const payload = decode ? JSON.parse(pkt.payload) : pkt.payload;
        try {
          if (this.cfg.onData) this.cfg.onData({ topic: pkt.topic, payload });
        } catch (e) {
          console.log('An error occured during onData execution', e);
        }
      } catch (e) {
        console.log('bad payload from', pkt.topic, e);
      }
    });

    try {
      await new Promise((resolve, reject) => {
        let timeout = stateTimeout * qps;
        const subscriptions = [
          ...this.cfg.subscriptions,
          { topic: `site/${this.cfg?.siteid}/${this.clientId}`, qos: 0 },
          { topic: `site/${this.cfg?.siteid}/${this.clientId}/#`, qos: 0 },
          { topic: `viewer/${this.clientId}`, qos: 0 },
        ];
        console.log('subscribe to', subscriptions);
        conn.on('suback', msg => {
          console.log('subscribed in', (stateTimeout - timeout / qps).toFixed(1), msg);
          resolve();
        });
        conn.subscribe({ messageId: this.messageId++, subscriptions });
        const check = () => {
          if (timeout <= 0 || ws.readyState > 1 || !this.url) return reject();

          timeout--;
          this.timeout = setTimeout(check, timeoutQuantum);
        };
        this.timeout = setTimeout(check, timeoutQuantum);
      });
    } catch (e) {
      return this._reconnect();
    }
    if (this.cfg.onConnect) this.cfg.onConnect();

    this.pinger = setInterval(() => this._ping(), 15000);
  }

  config(cfg) {
    this.cfg = { ...cfg };
    if (!this.ws && this.cfg.token) this._connect(); // NOTE: config function is not async
  }

  deleteMqttid() {
    if (this.clientId) {
      const mqttids = JSON.parse(localStorage.getItem('mqttids') || '{}');
      delete mqttids?.[this.clientId]?.active;
      localStorage.setItem('mqttids', JSON.stringify(mqttids));
    }
  }

  publish(...options) {
    if (this.conn) this.conn.publish(...options);
  }

  close(options) {
    const ws = this.ws;
    console.log('mqtt close');
    this.deleteMqttid();
    window.removeEventListener('beforeunload', this.deleteMqttid.bind(this));
    if (this.pinger) {
      clearInterval(this.pinger);
      delete this.pinger;
    }
    if (!options || !options.reconnect) {
      this.url = current.clientId = this.clientId = null;
      if (this.interval) {
        clearInterval(this.interval);
        delete this.interval;
      }
      if (this.reconnect) {
        clearTimeout(this.reconnect);
        delete this.reconnect;
      }
    } else {
      current.clientId = this.clientId = this.getMqttid();
      console.log('reconnecting...');
    }
    this.ws = this.conn = this.ip = null;
    try {
      if (ws) ws.terminate();
    } catch (e) {
      console.error('error closing ws', e);
    }
  }

  getMqttid() {
    const mqttids = JSON.parse(localStorage.getItem('mqttids') || '{}');
    const now = new Date();
    let id;
    for (const [mqttid, obj] of Object.entries(mqttids)) {
      if (obj.active && now - mqttid.ts > 7 * 86400000)
        // assume week-old entries are no longer active
        delete mqttids[mqttid];

      if (!obj.active) {
        obj.active = true;
        id = mqttid;
        break;
      }
    }
    if (!id) {
      id = nanoid();
      mqttids[id] = { active: true, ts: now };
    }
    localStorage.setItem('mqttids', JSON.stringify(mqttids));
    window.addEventListener('beforeunload', this.deleteMqttid.bind(this));
    return id;
  }

  async gcTimeout() {
    const now = Date.now();
    for (const [blockid, block] of Object.entries(this.blocks)) {
      if (now - block.ts > 60000) delete this.blocks[blockid];
    }
    this.gcTimer = setTimeout(this.gcTimeout.bind(this), 10000);
  }

  constructor() {
    // if (!window.mqtts) {
    //   window.mqtts = {};
    //   window.mqttcount = 0;
    // }
    // this.mqttid = window.mqttcount++;
    // window.mqtts[this.mqttid] = this;
    this.kickInterval = 500;
    this.reconnectInterval = 500;
    current.clientId = this.clientId = this.getMqttid();
    this.messageId = 1;
    this.blocks = {};
    this.gcTimer = setTimeout(this.gcTimeout.bind(this), 10000);
  }
}

export { MqttClient, current };

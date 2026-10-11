const { aes_siv } = require('./siv.js');

// sha256('alta has the best users')
const altakey = Buffer.from('9b12f4d4aff31d90a231af2e9061e9cd6c516ebd371945e0c5533a18c591b326', 'hex');

const REDIR_SITEID = 1;
const REDIR_PAYLOAD = 2;
const REDIR_SSIDID = 3;
const REDIR_NET = 4;
const REDIR_MAC = 5;
const REDIR_TS = 6;
const REDIR_APMAC = 7;
const REDIR_SSID = 8;

// Assume token is in base64 format (the way it is given to the client)
// Assume iappkey is in hexadecimal format
const verify = async ({ token, iappkey, ignore_ts = false }) => {
  let siteid, ssidid, net, mac, ts, apmac, ssid, expired = false;

  const enc2 = aes_siv(altakey, Buffer.from(token, 'base64'));
  let aadLen;

  for (let idx = 0; !aadLen && idx < enc2.length; ) {
    const type = enc2[idx++];
    let len = enc2[idx++];
    switch (type) {
      case REDIR_SITEID: siteid = enc2.slice(idx, idx + len).toString(); break;
      case REDIR_PAYLOAD:
        len <<= 8; len |= enc2[idx++];
        aadLen = idx;
        break;
      default: throw new Error('unknown type');
    }
    idx += len;
  }
  console.log('Site ID:', siteid);

  let plain = aes_siv(Buffer.from(iappkey, 'hex'), enc2.slice(aadLen), enc2.slice(0, aadLen));

  for (let idx = 0; idx < plain.length; ) {
    const type = plain[idx++];
    const len = plain[idx++];
    switch (type) {
      case REDIR_SSIDID: ssidid = plain.slice(idx, idx + len); break;
      case REDIR_NET: net = plain.slice(idx, idx + len); break;
      case REDIR_MAC: mac = plain.slice(idx, idx + len); break;
      case REDIR_TS: ts = plain.readInt32BE(idx); break;
      case REDIR_APMAC: apmac = plain.slice(idx, idx + len); break;
      case REDIR_SSID: ssid = plain.slice(idx, idx + len); break;
      default: throw new Error('unknown type2');
    }
    idx += len;
  }

  if (!ignore_ts) {
    let tsDiff = new Date().getTime() / 1000 - ts;
    if (tsDiff > 15 * 60)
      expired = Math.floor(tsDiff);
  }

  if (!ssidid || !net || !mac)
    throw new Error('Missing input', ssidid, net, mac);

  console.log('Token:');
  console.log('SSID ID:', ssidid?.toString());
  console.log('Net ID:', net?.toString());
  console.log('Client MAC:', mac.toString('hex'));
  console.log('AP MAC:', apmac.toString());
  console.log('SSID:', ssid.toString());
  console.log('Timestamp:', ts);
  console.log('Expired:', expired ? `${expired} seconds ago` : 'no');
};

module.exports = { verify };

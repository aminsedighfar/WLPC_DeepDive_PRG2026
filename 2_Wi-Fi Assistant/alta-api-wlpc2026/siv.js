const crypto = require('crypto');

// Heavily modified from https://github.com/allan-stewart/node-aes-cmac and
// hostapd C source

const AES_BLOCK_SIZE = 16;

let zero = Buffer.alloc(AES_BLOCK_SIZE);
let const_Rb = Buffer.alloc(AES_BLOCK_SIZE);
const_Rb[15] = 0x87;

const buf_shift_left = (buf) => {
  let shifted = Buffer.alloc(buf.length);
  let last = buf.length - 1;
  for (let i = 0; i < last; i++) {
    shifted[i] = buf[i] << 1;
    if (buf[i + 1] & 0x80)
      shifted[i] += 0x01;
  }
  shifted[last] = buf[last] << 1;
  return shifted;
};

const xor = (a, b) => {
  for (let i = 0; i < AES_BLOCK_SIZE; i++)
    a[i] ^= b[i];
};

const get_subkeys = function (key) {
  let l = aes(key, zero);

  let subkey1 = buf_shift_left(l);
  if (l[0] & 0x80)
    xor(subkey1, const_Rb);

  let subkey2 = buf_shift_left(subkey1);
  if (subkey1[0] & 0x80)
    xor(subkey2, const_Rb);

  return [ subkey1, subkey2 ];
};

const aes = (key, msg) => {
  let keyName = { 16: 'aes128', 24: 'aes192', 32: 'aes256' };
  if (!keyName[key.length])
    throw new Error(`Bad key length ${key.length}`);
  let cipher = crypto.createCipheriv(keyName[key.length], key, zero);
  let result = cipher.update(msg);
  cipher.final();
  return result;
}

const aes_cmac = function (key, msg) {
  let subkeys = get_subkeys(key);
  let blocks = Math.ceil(msg.length / AES_BLOCK_SIZE);
  let blockAligned, lastBlock, lastBlockIndex;

  if (blocks === 0) // 0-length msg?
    blocks = 1;

  blockAligned = (msg.length % AES_BLOCK_SIZE === 0);
  lastBlockIndex = blocks - 1;

  lastBlock = get_block(msg, lastBlockIndex);
  xor(lastBlock, subkeys[blockAligned ? 0 : 1]);

  let x = Buffer.alloc(AES_BLOCK_SIZE);

  for (let i = 0; i < lastBlockIndex; i++) {
    xor(x, get_block(msg, i));
    x = aes(key, x);
  }
  xor(lastBlock, x);
  return aes(key, lastBlock);
};

function get_block(msg, blockIndex) {
  return pad_block(msg.slice(blockIndex * AES_BLOCK_SIZE));
}

const dbl = (pad) => {
  const carry = pad[0] & 0x80;
  for (let i = 0; i < AES_BLOCK_SIZE - 1; i++)
    pad[i] = (pad[i] << 1) | (pad[i + 1] >> 7);
  pad[AES_BLOCK_SIZE - 1] <<= 1;
  if (carry)
    pad[AES_BLOCK_SIZE - 1] ^= 0x87;
};

const xorend = (a, b) => {
  if (a.length < b.length)
    return;
  for (let i = 0; i < b.length; i++)
    a[a.length - b.length + i] ^= b[i];
};

const pad_block = (block) => {
  const pad = Buffer.alloc(AES_BLOCK_SIZE, block);
  if (block.length < AES_BLOCK_SIZE) {
    pad[block.length] = 0x80;
    pad.fill(0, block.length + 1, AES_BLOCK_SIZE);
  }
  return pad;
}

const aes_siv = (key, crypt, aad) => {
  let k1 = key.slice(0, key.length / 2);
  let k2 = key.slice(key.length / 2);
  let iv = Buffer.alloc(AES_BLOCK_SIZE, crypt);
  iv[8] &= 0x7f;
  iv[12] &= 0x7f;
  let ctr = crypto.createCipheriv('aes-128-ctr', k2, iv);
  let plain = Buffer.concat([ctr.update(crypt.slice(AES_BLOCK_SIZE)), ctr.final()]);
  let check;

  let tmp = aes_cmac(k1, Buffer.alloc(AES_BLOCK_SIZE));

  if (aad) {
    let tmp2 = aes_cmac(k1, aad);
    dbl(tmp);
    xor(tmp, tmp2);
  }

  if (plain.length >= AES_BLOCK_SIZE) {
    let buf = Buffer.alloc(plain.length, plain);
    xorend(buf, tmp);
    check = aes_cmac(k1, buf);
  } else {
    console.log('NOTE: This code has never been tested!');
    dbl(tmp);
    let tmp2 = pad_block(plain);
    xor(tmp, tmp2);
    check = aes_cmac(k1, tmp);
  }

  if (!check.equals(crypt.slice(0, AES_BLOCK_SIZE)))
    throw new Error('bad mac');

  return plain;
}

module.exports = { aes_siv };

const assert = require('node:assert/strict');
const fs = require('node:fs');
const tls = require('node:tls');

async function main() {
  const [modulePath, keyPath, certPath] = process.argv.slice(2);
  const {sendSmtpMessage} = require(modulePath);
  const transcript = [];
  let data = '';
  const server = tls.createServer({key: fs.readFileSync(keyPath), cert: fs.readFileSync(certPath)}, socket => {
    socket.setEncoding('utf8');
    socket.write('220 local.test ESMTP ready\r\n');
    let buffer = '', authStep = 0, inData = false;
    socket.on('data', chunk => {
      buffer += chunk;
      if (inData) {
        const end = buffer.indexOf('\r\n.\r\n');
        if (end < 0) return;
        data += buffer.slice(0, end); buffer = buffer.slice(end + 5); inData = false;
        socket.write('250 queued\r\n');
      }
      while (!inData && buffer.includes('\r\n')) {
        const end = buffer.indexOf('\r\n');
        const line = buffer.slice(0, end); buffer = buffer.slice(end + 2); transcript.push(line);
        if (line.startsWith('EHLO')) socket.write('250-local.test\r\n250 AUTH LOGIN\r\n');
        else if (line === 'AUTH LOGIN') { authStep = 1; socket.write('334 VXNlcm5hbWU6\r\n'); }
        else if (authStep === 1) { authStep = 2; socket.write('334 UGFzc3dvcmQ6\r\n'); }
        else if (authStep === 2) { authStep = 0; socket.write('235 authenticated\r\n'); }
        else if (line.startsWith('MAIL FROM:') || line.startsWith('RCPT TO:')) socket.write('250 ok\r\n');
        else if (line === 'DATA') { inData = true; socket.write('354 send data\r\n'); }
        else if (line === 'QUIT') { socket.write('221 bye\r\n'); socket.end(); }
      }
    });
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  try {
    await sendSmtpMessage(
      {host: '127.0.0.1', port, secure: true, username: 'user@example.test', password: 'secret', rejectUnauthorized: false},
      {from: 'user@example.test', to: 'privacy@example.test', subject: 'Access request', body: 'Line one\n.dot line', messageId: '<smoke@gdpr-agent.local>'}
    );
  } finally {
    await new Promise(resolve => server.close(resolve));
  }
  assert.ok(transcript.includes(Buffer.from('user@example.test').toString('base64')));
  assert.ok(transcript.includes(Buffer.from('secret').toString('base64')));
  assert.ok(transcript.some(line => line === 'MAIL FROM:<user@example.test>'));
  assert.match(data, /Subject: Access request/);
  assert.match(data, /\r\n\.\.dot line/);
  console.log(JSON.stringify({tls: true, authenticated: true, accepted: true, dotStuffed: true}));
}

main().catch(error => { console.error(error); process.exitCode = 1; });

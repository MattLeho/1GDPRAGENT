import tls from 'tls';

export interface SmtpTransportConfiguration {
    host:string;port:number;secure:boolean;username:string;password:string;
    /** Test-only trust override; production callers leave this undefined. */
    rejectUnauthorized?:boolean;
}
export interface SmtpMessage {from:string;to:string;subject:string;body:string;messageId:string}

function cleanHeader(value:string):string{return value.replace(/[\r\n]+/g,' ');}

export async function sendSmtpMessage(configuration:SmtpTransportConfiguration,message:SmtpMessage):Promise<void>{
    if(!configuration.secure)throw new Error('Built-in SMTP requires TLS; plaintext AUTH is not permitted');
    if(!configuration.host||!configuration.port||!configuration.username||!configuration.password)throw new Error('SMTP configuration is incomplete');
    const body=message.body.replace(/\r?\n/g,'\r\n').replace(/^\./gm,'..');
    const socket=tls.connect({
        host:configuration.host,port:configuration.port,servername:configuration.host,
        rejectUnauthorized:configuration.rejectUnauthorized!==false,
    });
    try{await smtpProtocol(socket,[
        {expect:/^220/m,send:`EHLO gdpr-agent.local\r\n`},{expect:/^250[ -]/m,send:`AUTH LOGIN\r\n`},
        {expect:/^334/m,send:`${Buffer.from(configuration.username).toString('base64')}\r\n`},
        {expect:/^334/m,send:`${Buffer.from(configuration.password).toString('base64')}\r\n`},
        {expect:/^235/m,send:`MAIL FROM:<${cleanHeader(message.from)}>\r\n`},
        {expect:/^250/m,send:`RCPT TO:<${cleanHeader(message.to)}>\r\n`},
        {expect:/^250/m,send:'DATA\r\n'},
        {expect:/^354/m,send:`From: ${cleanHeader(message.from)}\r\nTo: ${cleanHeader(message.to)}\r\nSubject: ${cleanHeader(message.subject)}\r\nMessage-ID: ${cleanHeader(message.messageId)}\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n${body}\r\n.\r\n`},
        {expect:/^250/m,send:'QUIT\r\n'},{expect:/^221/m,send:null},
    ]);}finally{socket.destroy();}
}

function smtpProtocol(socket:tls.TLSSocket,steps:Array<{expect:RegExp;send:string|null}>):Promise<string>{return new Promise((resolve,reject)=>{
    let all='';let pending='';let index=0;let settled=false;
    const finish=(error?:Error)=>{if(settled)return;settled=true;clearTimeout(timeout);if(error)reject(error);else resolve(all)};
    const timeout=setTimeout(()=>{socket.destroy();finish(new Error('Email transport timed out'));},20_000);
    socket.setEncoding('utf8');socket.on('error',error=>finish(error));socket.on('data',chunk=>{all+=chunk;pending+=chunk;
        while(index<steps.length&&steps[index].expect.test(pending)){const step=steps[index++];pending='';if(step.send)socket.write(step.send);if(index===steps.length)finish();}
    });socket.on('close',()=>{if(!settled&&index<steps.length)finish(new Error('SMTP connection closed before completion'));});
  });}

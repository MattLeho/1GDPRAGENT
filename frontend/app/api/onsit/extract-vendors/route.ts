import { NextRequest,NextResponse } from 'next/server';
import { mkdir,unlink,writeFile } from 'fs/promises';import path from 'path';import crypto from 'crypto';
import { executeTask } from '@/lib/execution/router';

export async function POST(request:NextRequest){
    let temporary:string|null=null;
    try{
        const contentType=request.headers.get('content-type')||'';let type:'image'|'video'|'text';let data:string;
        if(contentType.includes('multipart/form-data')){const form=await request.formData();const file=form.get('video');if(!(file instanceof File))return NextResponse.json({success:false,error:'No video file provided'},{status:400});type='video';data=`data:${file.type};base64,${Buffer.from(await file.arrayBuffer()).toString('base64')}`;}
        else{const body=await request.json();type=body.type;data=body.data;}
        let text=data;
        if(type!=='text'){
            const match=data.match(/^data:([^;]+);base64,([\s\S]+)$/);if(!match)throw new Error('Image/video must be a data URL');
            const uploadDir=process.env.UPLOAD_DIR||path.join(process.cwd(),'uploads','task-router');await mkdir(uploadDir,{recursive:true});temporary=path.join(uploadDir,`${crypto.randomUUID()}.${type==='video'?'mp4':'png'}`);await writeFile(temporary,Buffer.from(match[2],'base64'));
            const intelligencePath=temporary.startsWith('/app/uploads/')?temporary.replace('/app/uploads/','/source-uploads/'):temporary;
            const ocr=await executeTask({taskKey:'image.ocr',workflowKey:'vendor.ocr',input:{file_path:intelligencePath,mime_type:match[1]}});
            if(!ocr.ok)throw new Error(ocr.error.message);text=String((ocr.output as {text?:unknown}).text||'');
        }
        const adjudication=await executeTask({taskKey:'semantic.adjudication',workflowKey:'vendor.ocr',input:{text},configuration:{systemPrompt:'Extract company or vendor names visible in this cookie-consent text. Return only a JSON array of unique names. Do not infer names that are absent.'}});
        if(!adjudication.ok)throw new Error(adjudication.error.message);const output=String((adjudication.output as {text?:unknown}).text||'');const match=output.match(/\[[\s\S]*\]/);const vendors=match?JSON.parse(match[0]):[];
        return NextResponse.json({success:true,vendors:Array.isArray(vendors)?vendors:[],count:Array.isArray(vendors)?vendors.length:0});
    }catch(error){return NextResponse.json({success:false,error:error instanceof Error?error.message:String(error)},{status:422});}
    finally{if(temporary)await unlink(temporary).catch(()=>undefined);}
}

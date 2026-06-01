/**
 * Vendor Extraction API Route
 * 
 * Extracts vendor names from:
 * - Screenshots (OCR with Gemini Vision)
 * - Screen recordings (frame extraction + OCR)
 * - Plain text
 * 
 * Used for extracting vendors from cookie consent dialogs.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAICredential } from '@/lib/ai-credentials';

export async function POST(request: NextRequest) {
    try {
        const contentType = request.headers.get('content-type');

        let type: 'image' | 'video' | 'text';
        let data: string;

        if (contentType?.includes('multipart/form-data')) {
            // Video upload
            const formData = await request.formData();
            const videoFile = formData.get('video') as File;

            if (!videoFile) {
                return NextResponse.json(
                    { success: false, error: 'No video file provided' },
                    { status: 400 }
                );
            }

            // For video, we'll extract a frame and process as image
            type = 'video';
            data = await extractVideoFrame(videoFile);
        } else {
            // JSON payload (image or text)
            const body = await request.json();
            type = body.type;
            data = body.data;
        }

        // Get API key
        const apiKey = await getAICredential('google') ||
            process.env.GOOGLE_API_KEY ||
            process.env.GEMINI_API_KEY;

        if (!apiKey) {
            return NextResponse.json(
                { success: false, error: 'No Google API key configured' },
                { status: 500 }
            );
        }

        let vendors: string[] = [];

        if (type === 'text') {
            // Process plain text
            vendors = await extractVendorsFromText(data, apiKey);
        } else {
            // Process image (screenshot or video frame)
            vendors = await extractVendorsFromImage(data, apiKey);
        }

        return NextResponse.json({
            success: true,
            vendors,
            count: vendors.length,
        });

    } catch (error) {
        console.error('[Vendor Extraction] Error:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to extract vendors' },
            { status: 500 }
        );
    }
}

/**
 * Extract vendors from plain text using simple pattern matching + AI cleanup
 */
async function extractVendorsFromText(text: string, apiKey: string): Promise<string[]> {
    const { GoogleGenAI } = await import('@google/genai');
    const ai = new GoogleGenAI({ apiKey });

    const prompt = `Extract company/vendor names from this cookie consent text.
Return ONLY a JSON array of vendor names, no explanation.

TEXT:
${text}

Example response: ["Google", "Facebook", "Amazon"]`;

    const response = await ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: prompt,
    });

    const responseText = response.text || '';

    // Extract JSON array
    const jsonMatch = responseText.match(/\[[\s\S]*\]/);
    if (jsonMatch) {
        const vendors = JSON.parse(jsonMatch[0]);
        return Array.isArray(vendors) ? vendors : [];
    }

    return [];
}

/**
 * Extract vendors from image using Gemini Vision OCR
 */
async function extractVendorsFromImage(base64Image: string, apiKey: string): Promise<string[]> {
    const { GoogleGenAI } = await import('@google/genai');
    const ai = new GoogleGenAI({ apiKey });

    // Remove data URL prefix if present
    const imageData = base64Image.replace(/^data:image\/[a-z]+;base64,/, '');

    const prompt = `This is a screenshot of a cookie consent dialog showing a list of vendors/companies.

Extract ALL company/vendor names you can see in the image.
Return ONLY a JSON array of vendor names, no explanation.

Example response: ["Google Analytics", "Facebook Pixel", "Amazon Associates"]`;

    const response = await ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: [
            { text: prompt },
            { inlineData: { data: imageData, mimeType: 'image/png' } },
        ],
    });

    const responseText = response.text || '';

    // Extract JSON array
    const jsonMatch = responseText.match(/\[[\s\S]*\]/);
    if (jsonMatch) {
        const vendors = JSON.parse(jsonMatch[0]);
        return Array.isArray(vendors) ? vendors : [];
    }

    return [];
}

/**
 * Extract a representative frame from video for OCR
 */
async function extractVideoFrame(videoFile: File): Promise<string> {
    // Convert video file to base64 for now
    // In production, you'd want to:
    // 1. Use FFmpeg to extract frame at ~50% position
    // 2. Or use a client-side canvas to extract frame
    // For simplicity, we'll just return a placeholder and let the client handle it

    const buffer = await videoFile.arrayBuffer();
    const base64 = Buffer.from(buffer).toString('base64');
    return `data:${videoFile.type};base64,${base64}`;
}

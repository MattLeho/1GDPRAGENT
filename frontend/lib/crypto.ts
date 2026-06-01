import CryptoJS from 'crypto-js';

const SALT = 'gdpr-local-salt'; // In a real app, this should be more secure/dynamic

/**
 * Encrypts a string using AES encryption
 * @param text The text to encrypt
 * @param key The encryption key (user password/passphrase)
 * @returns Encrypted string
 */
export const encryptData = (text: string, key: string): string => {
    if (!text || !key) return '';
    // Combine key with salt for slightly better entropy
    const saltedKey = key + SALT;
    return CryptoJS.AES.encrypt(text, saltedKey).toString();
};

/**
 * Decrypts a string using AES encryption
 * @param ciphertext The encrypted text
 * @param key The decryption key
 * @returns Decrypted string or empty string if failed
 */
export const decryptData = (ciphertext: string, key: string): string => {
    if (!ciphertext || !key) return '';
    try {
        const saltedKey = key + SALT;
        const bytes = CryptoJS.AES.decrypt(ciphertext, saltedKey);
        return bytes.toString(CryptoJS.enc.Utf8);
    } catch (error) {
        console.error('Decryption failed:', error);
        return '';
    }
};

export const GIF_LIMIT = 5 * 1024 * 1024;
export function validateIllustration(value) {
  if (value == null) return null;
  if (typeof value !== 'object' || typeof value.name !== 'string' || typeof value.dataUrl !== 'string'
      || value.dataUrl.length > Math.ceil(GIF_LIMIT / 3) * 4 + 22
      || !/^data:image\/gif;base64,[A-Za-z0-9+/]+={0,2}$/.test(value.dataUrl))
    throw new Error('Choose a GIF image of 5 MB or less.');
  let bytes;
  try { bytes = atob(value.dataUrl.slice('data:image/gif;base64,'.length)); }
  catch { throw new Error('The GIF image is damaged.'); }
  if (bytes.length > GIF_LIMIT || bytes.length < 13 || !['GIF87a','GIF89a'].includes(bytes.slice(0,6)))
    throw new Error('This file is not a valid GIF image.');
  const width = bytes.charCodeAt(6) | bytes.charCodeAt(7) << 8;
  const height = bytes.charCodeAt(8) | bytes.charCodeAt(9) << 8;
  if (!width || !height || width * height > 16000000) throw new Error('Choose a GIF with dimensions below 16 megapixels.');
  return {name:value.name.slice(0,200), dataUrl:value.dataUrl};
}
export async function readIllustration(file) {
  if (!file || file.size > GIF_LIMIT) throw new Error('Choose a GIF image of 5 MB or less.');
  const dataUrl = await new Promise((resolve,reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('Could not read this file.'));
    reader.readAsDataURL(new Blob([file], {type:'image/gif'}));
  });
  const illustration = validateIllustration({name:file.name, dataUrl});
  const image = new Image(); image.src = illustration.dataUrl;
  try { await image.decode(); } catch { throw new Error('The GIF could not be opened. Choose another image.'); }
  return illustration;
}

import type { DocumentService, DmsContext, DmsVersion, DmsArtifact, DmsImageContext, DmsImage } from '../reference/DocumentService.ts';
/** Service credential stays in trusted server code; artifact URLs require Authorization. */
export class HttpDocumentService implements DocumentService {
  constructor(private origin: string, private credential: string, readonly fixture: boolean, private transport: typeof fetch = fetch) {
    const url = new URL(origin);
    if (url.protocol !== 'https:' && !(fixture && url.hostname === '127.0.0.1' && url.protocol === 'http:')) throw new Error('HTTPS required');
  }
  private async call<T>(path: string, body?: unknown): Promise<T> {
    const r = await this.transport(new URL(path, this.origin), {method: body === undefined ? 'GET' : 'POST', headers: {Authorization: `Bearer ${this.credential}`, 'Content-Type': 'application/json'}, ...(body === undefined ? {} : {body: JSON.stringify(body)})});
    if (!r.ok) throw new Error(`document_service_${r.status}`);
    const data = await r.json();
    for (const item of Array.isArray(data) ? data : [data]) {
      if (item && 'fixture' in item && item.fixture !== this.fixture) throw new Error('document_fixture_mode_mismatch');
    }
    return data as T;
  }
  upload(context: DmsContext, input: {filename:string;contentType:string;contentBase64:string}): Promise<DmsVersion> { return this.call('/v1/uploads', {context,input}); }
  template(id:string,version:string): Promise<{id:string;version:string}> { return this.call(`/v1/templates/${encodeURIComponent(id)}/versions/${encodeURIComponent(version)}`); }
  generate(context:DmsContext,input:{templateId:string;templateVersion:string;snapshot:unknown}):Promise<DmsVersion> {return this.call('/v1/documents',{context,input});}
  versions(context:DmsContext):Promise<DmsVersion[]> {return this.call(`/v1/documents/${encodeURIComponent(context.documentId)}/versions?${this.query(context)}`);}
  signRequest(context:DmsContext,input:{versionId:string;signers:{name:string;email:string}[]}):Promise<{requestId:string;versionId:string}> {return this.call('/v1/signature-requests',{context,input});}
  update(context:DmsContext,input:{versionId:string;requestId:string}):Promise<{status:string}> {return this.call(`/v1/signature-requests/${encodeURIComponent(input.requestId)}/status`,{context,input});}
  artifacts(context:DmsContext,versionId:string):Promise<DmsArtifact[]> {return this.call(this.version(context,versionId)+`/artifacts?${this.query(context)}`);}
  image(context:DmsImageContext,versionId:string):Promise<DmsImage> {return this.call(this.version(context,versionId)+`/image?${this.query(context)}`);}
  private query(context:DmsContext):string { return new URLSearchParams({...context}).toString(); }
  private version(context:DmsContext,id:string):string {return `/v1/documents/${encodeURIComponent(context.documentId)}/versions/${encodeURIComponent(id)}`;}
  async download(artifact:DmsArtifact):Promise<ArrayBuffer> {
    const url = new URL(artifact.url);
    if (url.origin !== new URL(this.origin).origin) throw new Error('artifact_origin_mismatch');
    const r=await this.transport(url,{headers:{Authorization:`Bearer ${this.credential}`}});
    if (!r.ok) throw new Error(`document_download_${r.status}`);
    return r.arrayBuffer();
  }
}

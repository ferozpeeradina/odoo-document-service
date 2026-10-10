import type { DocumentService, DmsContext, DmsVersion, DmsArtifact, DmsImageContext, DmsImage } from '../reference/DocumentService.ts';

/** Sandbox provider: session authentication is supplied by the trusted caller.
 * The adapter stores no snapshots, versions, signing links, or evidence.
 */
export class OdooDocumentService implements DocumentService {
  readonly fixture = true;
  private readonly baseUrl: string;
  private readonly transport: typeof fetch;
  constructor(baseUrl: string, transport: typeof fetch = fetch) {
    this.baseUrl = baseUrl;
    this.transport = transport;
    const url = new URL(baseUrl);
    if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || url.port !== '18069') {
      throw new Error('This proof of concept permits only http://127.0.0.1:18069');
    }
  }
  private async call<T>(method: string, context: DmsContext | undefined, input: unknown): Promise<T> {
    const response = await this.transport(new URL('/poc/api', this.baseUrl), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'call', params: { method, context, input } }),
      credentials: 'include',
    });
    if (!response.ok) throw new Error(`odoo_http_${response.status}`);
    const body = await response.json();
    if (body.error) throw new Error('odoo_authenticated_request_failed');
    if (body.result?.error) throw new Error(body.result.error.code);
    if (!body.result || !('data' in body.result)) throw new Error('odoo_invalid_response');
    return body.result.data as T;
  }
  upload(context: DmsContext, input: {filename: string; contentType: string; contentBase64: string}): Promise<DmsVersion> {
    return this.call('upload', context, input);
  }
  template(id: string, version: string): Promise<{id: string; version: string}> {
    return this.call('template', undefined, { id, version });
  }
  generate(context: DmsContext, input: {templateId: string; templateVersion: string; snapshot: unknown}): Promise<DmsVersion> {
    return this.call('generate', context, input);
  }
  versions(context: DmsContext): Promise<DmsVersion[]> { return this.call('versions', context, {}); }
  signRequest(context: DmsContext, input: {versionId: string; signers: {name: string; email: string}[]}): Promise<{requestId: string; versionId: string}> {
    return this.call('signRequest', context, input);
  }
  update(context: DmsContext, input: {versionId: string; requestId: string}): Promise<{status: string}> { return this.call('update', context, input); }
  async artifacts(context: DmsContext, versionId: string): Promise<DmsArtifact[]> {
    const result = await this.call<DmsArtifact[]>('artifacts', context, { versionId });
    return result.map(a => ({ ...a, url: new URL(a.url, this.baseUrl).href }));
  }
  image(context: DmsImageContext, versionId: string): Promise<DmsImage> { return this.call('image', context, { versionId }); }
}

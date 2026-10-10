export interface DmsContext {tenantId:string;documentId:string;projectId?:string;operationId:string;localDocumentId?:string}
export interface DmsVersion {tenantId:string;documentId:string;projectId?:string;versionId:string;fixture:boolean;localDocumentId?:string}
export interface DmsArtifact extends DmsVersion {kind:'document'|'signed_document'|'evidence';url:string}
export interface DmsImageContext extends DmsContext {actorId:string;localDocumentId:string}
export interface DmsImage extends DmsVersion {actorId:string;localDocumentId:string;contentType:'image/png'|'image/jpeg'|'image/webp';contentBase64:string}
export interface DocumentService {
 readonly fixture:boolean;
 upload(context:DmsContext,input:{filename:string;contentType:string;contentBase64:string}):Promise<DmsVersion>;
 template(id:string,version:string):Promise<{id:string;version:string}>;
 generate(context:DmsContext,input:{templateId:string;templateVersion:string;snapshot:unknown}):Promise<DmsVersion>;
 versions(context:DmsContext):Promise<DmsVersion[]>;
 signRequest(context:DmsContext,input:{versionId:string;signers:{name:string;email:string}[]}):Promise<{requestId:string;versionId:string}>;
 update(context:DmsContext,input:{versionId:string;requestId:string}):Promise<{status:string}>;
 artifacts(context:DmsContext,versionId:string):Promise<DmsArtifact[]>;
 image?(context:DmsImageContext,versionId:string):Promise<DmsImage>;
}

"""Comment UI and portable Word export embedded in the original draft template."""

CSS = """
#comments-dialog{color:var(--ink);background:var(--bg);border:1px solid var(--line);
  position:fixed;inset:auto;margin:0;box-sizing:border-box;z-index:36;
  border-radius:8px;width:min(24rem,94vw);max-height:min(65vh,34rem);padding:1rem;
  box-shadow:0 8px 28px #29241e26}
#comment-add{position:fixed;z-index:35;color:var(--ink);display:grid;place-items:center;
  width:32px;height:32px;padding:0;box-shadow:0 2px 8px #29241e26}
#comment-add[hidden]{display:none}
#comment-add:hover{background:var(--hover)}
#reattach-comments{color:var(--comment-link);white-space:nowrap}
.comment-add-icon{position:relative;display:grid;place-items:center;box-sizing:border-box;
  width:18px;height:14px;margin-bottom:3px;border:1.5px solid currentColor;border-radius:4px;
  font:600 12px/1 system-ui,sans-serif;background:inherit}
.comment-add-icon::after{content:'';position:absolute;left:3px;bottom:-4px;width:4px;height:4px;
  border-left:1.5px solid currentColor;border-bottom:1.5px solid currentColor;
  transform:skewY(-38deg);background:inherit}
#comments-dialog:modal{inset:0;margin:auto}
#comments-dialog label{font-size:13px}
#comments-dialog h2{font-size:17px;margin:0 0 1rem}
#comments-dialog textarea{width:100%;min-height:5rem;box-sizing:border-box;
  font:15px/1.5 Georgia,serif;padding:.6rem;margin:.5rem 0}
#comments-dialog blockquote{margin:.6rem 0;color:var(--heading);white-space:pre-wrap}
#comments-dialog .comment{border-top:1px solid var(--line);padding:.7rem 0}
/* Keep the highlight blue even where it blends with the gold reading highlight. */
#comment-marks{position:absolute;inset:0;overflow:hidden;pointer-events:none;mix-blend-mode:multiply;
  --comment-fill:#bfd2ff;--comment-underline:#38638d}
:root[data-theme="dark"] #comment-marks{mix-blend-mode:screen;--comment-fill:#123455;--comment-underline:#85badf}
#comment-marks span{position:absolute;background:var(--comment-fill);border-bottom:2px solid var(--comment-underline)}
#comments-dialog .comment p{white-space:pre-wrap;overflow-wrap:anywhere}
#comment-message{font-size:13px;color:var(--heading)}
#comment-message:empty,#comment-selection:empty{display:none}
#comments-dialog .actions{display:flex;justify-content:flex-end;gap:.5rem}
"""

HTML = """
<button id="comment-add" type="button" class="act" aria-label="Add comment" title="Add comment" hidden>
  <span class="comment-add-icon" aria-hidden="true">+</span>
</button>
<dialog id="comments-dialog" aria-labelledby="comments-title">
  <h2 id="comments-title">Add comment</h2>
  <div id="comment-list"></div>
  <p id="comment-message" role="status"></p>
  <form id="comment-form">
    <blockquote id="comment-selection"></blockquote>
    <label id="comment-label" for="comment-text">Comment</label>
    <textarea id="comment-text" maxlength="20000"></textarea>
  </form>
  <div class="actions"><button type="button" onclick="closeComments()">close</button>
  <button id="save-comment" type="submit" form="comment-form" class="act">save comment</button></div>
</dialog>
"""

JS = r"""
const NKEY='__PFX__draft:comments', AUTHOR_KEY='__PFX__draft:comment-author';
const authorField=document.getElementById('comment-author');
authorField.value=localStorage.getItem(AUTHOR_KEY)||'';
authorField.addEventListener('input',()=>localStorage.setItem(AUTHOR_KEY,authorField.value));
let comments=readComments(), annotationText='', commentSelection=null;
let editingComment=null, activeCommentIDs=[], recoveringComments=false, selectedQuote='';
let commentRanges=[];
const commentDialog=document.getElementById('comments-dialog');
const commentField=document.getElementById('comment-text');
const commentForm=commentField.form;
const commentSubmit=document.getElementById('save-comment');
const commentAdd=document.getElementById('comment-add');
const reattachButton=document.getElementById('reattach-comments');
const commentMarks=document.getElementById('comment-marks');
function readComments(){try{return JSON.parse(localStorage.getItem(NKEY)||'{}')}catch{return{}}}
function chapterComments(){return comments[cur]||[]}
function attachedComments(){return chapterComments().filter(note=>!note.detached)}
/* Keep anchors stable for edits wholly before or after the passage. An edit
   through the passage detaches its note instead of silently attaching elsewhere. */
function trackCommentEdits(){
  const before=annotationText, after=ta.value;
  if(before===after)return;
  let start=0;
  while(start<before.length&&start<after.length&&before[start]===after[start])start++;
  let oldEnd=before.length, newEnd=after.length;
  while(oldEnd>start&&newEnd>start&&before[oldEnd-1]===after[newEnd-1]){oldEnd--;newEnd--}
  const delta=newEnd-oldEnd;
  if(commentDialog.open&&commentSelection?.start<commentSelection?.end&&oldEnd<=commentSelection.start){
    commentSelection.start+=delta;commentSelection.end+=delta;
  }
  for(const note of chapterComments()){
    if(note.detached)continue;
    if(oldEnd<=note.start){note.start+=delta;note.end+=delta}
    else if(start<note.end)note.detached=true;
  }
  annotationText=after;
}
function drawCommentHighlights(){
  const detachedCount=chapterComments().filter(note=>note.detached).length;
  reattachButton.hidden=!detachedCount;
  if(detachedCount)reattachButton.textContent=detachedCount===1?'1 comment to reattach':detachedCount+' comments to reattach';
  const notes=attachedComments();
  const snapshot=notes.length?editorSnapshot():null;
  commentRanges=notes.map(note=>({note,range:editorRange(note.start,note.end,snapshot)}));
  paintCommentHighlights();
}
function paintCommentHighlights(){
  const pane=commentMarks.getBoundingClientRect(), bounds=ta.getBoundingClientRect();
  const marks=document.createDocumentFragment();
  // Paint outside the editable DOM so the markers don't affect native editing or undo.
  for(const {range} of commentRanges){
    for(const rect of range.getClientRects()){
      const top=Math.max(rect.top,bounds.top), bottom=Math.min(rect.bottom,bounds.bottom);
      if(rect.width<=0||bottom<=top)continue;
      const mark=document.createElement('span');
      mark.style.left=(rect.left-pane.left)+'px';
      mark.style.top=(top-pane.top)+'px';
      mark.style.width=rect.width+'px';
      mark.style.height=(bottom-top)+'px';
      marks.append(mark);
    }
  }
  commentMarks.replaceChildren(marks);
}
ta.addEventListener('click',event=>{
  if(!getSelection()?.isCollapsed)return;
  const {clientX:x,clientY:y}=event;
  // The caret can land after the last letter even when the click is inside it.
  const hits=commentRanges.filter(({range})=>[...range.getClientRects()].some(rect=>
    x>=rect.left&&x<rect.right&&y>=rect.top&&y<rect.bottom));
  if(hits.length)openComments(hits.map(({note})=>note.id));
});
function selectedPassage(){
  const selection=getSelection();
  if(!selection?.anchorNode||!ta.contains(selection.anchorNode)||!ta.contains(selection.focusNode))return null;
  const start=ta.selectionStart,end=ta.selectionEnd;
  return start<end?{start,end}:null;
}
function passageBox(passage,bounds){
  if(!passage||passage.start>=passage.end)return null;
  const range=editorRange(passage.start,passage.end,editorSnapshot());
  const visible=[...range.getClientRects()].filter(rect=>rect.width&&rect.bottom>bounds.top&&rect.top<bounds.bottom);
  if(!visible.length)return null;
  const first=visible[0], midline=(first.top+first.bottom)/2;
  const firstLine=visible.filter(rect=>rect.top<=midline&&rect.bottom>=midline);
  return {top:Math.max(first.top,bounds.top),bottom:Math.min(visible.at(-1).bottom,bounds.bottom),
    right:Math.min(bounds.right,Math.max(...firstLine.map(rect=>rect.right))),
    rangeRight:Math.max(...visible.map(rect=>rect.right))};
}
function positionComments(){
  if(!commentDialog.open||recoveringComments)return;
  const note=chapterComments().find(note=>note.id===activeCommentIDs[0]);
  const bounds=ta.getBoundingClientRect();
  const anchor=passageBox(note&&!note.detached?note:commentSelection,bounds);
  if(!anchor){closeComments(false, false);return}
  positionPassageControl(commentDialog,anchor,bounds,12);
}
function positionPassageControl(control,anchor,bounds,gap){
  const leftEdge=bounds.left+gap, rightEdge=bounds.right-gap;
  const topEdge=bounds.top+gap, bottomEdge=bounds.bottom-gap;
  const dialog=control===commentDialog;
  if(dialog)control.style.maxWidth=Math.max(0,rightEdge-leftEdge)+'px';
  control.style.maxHeight='';
  const width=control.offsetWidth, height=control.offsetHeight;
  const above=anchor.top-gap, below=anchor.bottom+gap;
  const roomAbove=above-topEdge, roomBelow=bottomEdge-below;
  let left=anchor.right+gap, top=anchor.top-gap;
  if(left>=anchor.rangeRight&&left+width<=rightEdge){
    top=Math.max(topEdge,Math.min(top,bottomEdge-height));
  }else{
    left=Math.max(leftEdge,Math.min(anchor.right-width,rightEdge-width));
    if(roomAbove>=height)top=above-height;
    else if(roomBelow>=height)top=below;
    else if(dialog&&Math.max(roomAbove,roomBelow)>=120){
      top=roomAbove>=roomBelow?topEdge:below;
      control.style.maxHeight=Math.max(roomAbove,roomBelow)+'px';
    }else top=Math.max(topEdge,bottomEdge-height);
  }
  control.style.left=left+'px';
  control.style.top=top+'px';
}
function updateCommentButton(){
  const bounds=ta.getBoundingClientRect();
  const anchor=commentDialog.open?null:passageBox(selectedPassage(),bounds);
  commentAdd.hidden=!anchor;
  if(anchor)positionPassageControl(commentAdd,anchor,bounds,6);
  if(guidingComment())positionDraftHelp();
}
document.addEventListener('selectionchange',updateCommentButton);
ta.addEventListener('scroll',()=>{paintCommentHighlights();updateCommentButton();positionComments()},{passive:true});
addEventListener('resize',()=>{paintCommentHighlights();updateCommentButton();positionComments()});
commentAdd.addEventListener('mousedown',event=>event.preventDefault());
commentAdd.addEventListener('click',()=>openComments());
reattachButton.addEventListener('click',()=>openComments([],true));
document.addEventListener('pointerdown',event=>{
  if(!commentDialog.open)return;
  if(!recoveringComments&&!commentDialog.contains(event.target))closeComments(false,false);
  if(recoveringComments&&event.target===commentDialog){
    const rect=commentDialog.getBoundingClientRect();
    if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)closeComments();
  }
});
function openComments(ids=[],recovering=false){
  if(!closeComments(false))return;
  commentSelection={start:ta.selectionStart,end:ta.selectionEnd};
  selectedQuote=ta.value.slice(commentSelection.start,commentSelection.end);
  activeCommentIDs=ids;
  recoveringComments=recovering;
  editingComment=null;
  commentField.value='';
  renderComments();
  commentDialog.style.left=commentDialog.style.top=commentDialog.style.maxHeight=commentDialog.style.maxWidth='';
  if(recoveringComments)commentDialog.showModal();
  else commentDialog.show();
  updateCommentButton();
  positionComments();
  if(!commentForm.hidden)commentField.focus();
}
function closeComments(restoreFocus=true,ask=true){
  if(!commentDialog.open)return true;
  if(hasUnsavedComment()&&(!ask||!confirm('Discard the unsaved comment?')))return false;
  commentField.value='';
  commentDialog.close();
  if(restoreFocus)ta.focus();
  updateCommentButton();
  return true;
}
function hasUnsavedComment(){
  const original=chapterComments().find(note=>note.id===editingComment)?.text||'';
  return !commentForm.hidden&&commentField.value.trim()!==original;
}
function renderComments(){
  const list=document.getElementById('comment-list');list.replaceChildren();
  const title=document.getElementById('comments-title');
  title.textContent=recoveringComments?'Reattach comments':activeCommentIDs.length?'Comment':'Add comment';
  const notes=chapterComments().filter(note=>recoveringComments?note.detached:activeCommentIDs.includes(note.id));
  if(!notes.length&&(recoveringComments||activeCommentIDs.length)){closeComments();return}
  for(const note of notes){
    const card=document.createElement('section');card.className='comment';card.dataset.id=note.id;
    const quote=document.createElement('blockquote');quote.textContent=note.quote;
    const text=document.createElement('p');text.textContent=note.text;
    card.append(quote,text);
    for(const reply of note.replies||[]){
      const message=document.createElement('p');message.textContent=reply;card.append(message);
    }
    if(note.detached){const warning=document.createElement('p');warning.textContent='Passage changed. Select text in the draft, then reopen comments to reattach.';card.append(warning)}
    const action=(label,fn)=>{const button=document.createElement('button');button.type='button';button.textContent=label;button.onclick=fn;card.append(button)};
    action('edit',()=>{
      if(hasUnsavedComment()&&!confirm('Discard the unsaved comment?'))return;
      editingComment=note.id;commentField.value=note.text;
      renderCommentForm();positionComments();commentField.focus();
    });
    if(note.detached&&selectedQuote)action('reattach',()=>{
      if(hasUnsavedComment()&&!confirm('Discard the unsaved comment?'))return;
      if(!commentPassageStillMatches())return;
      editingComment=null;commentField.value='';
      Object.assign(note,commentSelection,{quote:ta.value.slice(commentSelection.start,commentSelection.end),detached:false});touch();commit();renderComments();
      if(!commentDialog.open)ta.setSelectionRange(note.end,note.end);
    });
    action('delete',()=>{
      if(!confirm('Delete this comment?'))return;
      comments[cur]=chapterComments().filter(n=>n.id!==note.id);
      if(editingComment===note.id){editingComment=null;commentField.value=''}
      touch();commit();
      if(!recoveringComments){
        activeCommentIDs=activeCommentIDs.filter(id=>id!==note.id);
        if(!activeCommentIDs.length){closeComments();return}
      }
      renderComments();
    });
    list.append(card);
  }
  renderCommentForm();
  positionComments();
}
function renderCommentForm(){
  const note=chapterComments().find(note=>note.id===editingComment);
  const shown=!!note||(!recoveringComments&&!activeCommentIDs.length);
  commentForm.hidden=commentSubmit.hidden=!shown;
  document.getElementById('comment-selection').textContent=note?'':selectedQuote;
  document.getElementById('comment-message').textContent='';
}
function commentPassageStillMatches(){
  if(selectedQuote&&ta.value.slice(commentSelection.start,commentSelection.end)===selectedQuote)return true;
  document.getElementById('comment-message').textContent='The selected text changed. Select it again to attach this comment.';
  return false;
}
commentField.addEventListener('input',recordEdit);
commentForm.addEventListener('submit',e=>{
  e.preventDefault();
  const field=document.getElementById('comment-text'), text=field.value.trim();
  if(!text){field.focus();return}
  const note=chapterComments().find(n=>n.id===editingComment);
  if(note)note.text=text;
  else {
    if(!commentSelection||commentSelection.end<=commentSelection.start||!commentPassageStillMatches())return;
    const created={id:crypto.randomUUID(),...commentSelection,
      quote:ta.value.slice(commentSelection.start,commentSelection.end),text,detached:false};
    (comments[cur]??=[]).push(created);
  }
  field.value='';editingComment=null;touch();commit();
  if(recoveringComments)renderComments();
  else closeComments();
});
document.addEventListener('keydown',event=>{
  if((event.metaKey||event.ctrlKey)&&event.shiftKey&&event.code==='KeyM'&&event.target===ta&&selectedPassage()){
    event.preventDefault();openComments();
  }else if(event.key==='Escape'&&commentDialog.open){
    event.preventDefault();event.stopPropagation();closeComments();
  }else if(event.target===commentField&&event.key==='Enter'&&!event.shiftKey&&!event.isComposing){
    event.preventDefault();
    commentForm.requestSubmit();
  }
});
addEventListener('beforeunload',e=>{if(commentDialog.open&&hasUnsavedComment()){e.preventDefault();e.returnValue=''}});

/* Minimal OOXML package, using uncompressed ZIP entries. This runs on file://
   as well as hosted pages, with no network requests or runtime dependencies. */
function wordXML(value){return String(value).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffe\uffff]/g,'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]))}
function wordRun(text,italic=false){return '<w:r>'+(italic?'<w:rPr><w:i/></w:rPr>':'')+'<w:t xml:space="preserve">'+wordXML(text)+'</w:t></w:r>'}
function wordZip(entries){
  const encoder=new TextEncoder(), chunks=[], central=[];let offset=0;
  const header=size=>new DataView(new ArrayBuffer(size));
  const crc=bytes=>{let n=0xffffffff;for(const byte of bytes){n^=byte;for(let i=0;i<8;i++)n=(n>>>1)^((n&1)?0xedb88320:0)}return (n^0xffffffff)>>>0};
  for(const [path,text] of entries){
    const name=encoder.encode(path), data=encoder.encode(text), checksum=crc(data);
    const local=header(30);local.setUint32(0,0x04034b50,true);local.setUint16(4,20,true);local.setUint16(12,33,true);
    local.setUint32(14,checksum,true);local.setUint32(18,data.length,true);local.setUint32(22,data.length,true);local.setUint16(26,name.length,true);
    chunks.push(local.buffer,name,data);
    const item=header(46);item.setUint32(0,0x02014b50,true);item.setUint16(4,20,true);item.setUint16(6,20,true);item.setUint16(14,33,true);
    item.setUint32(16,checksum,true);item.setUint32(20,data.length,true);item.setUint32(24,data.length,true);item.setUint16(28,name.length,true);item.setUint32(42,offset,true);
    central.push(item.buffer,name);offset+=30+name.length+data.length;
  }
  const size=central.reduce((n,c)=>n+c.byteLength,0), end=header(22);
  end.setUint32(0,0x06054b50,true);end.setUint16(8,entries.length,true);end.setUint16(10,entries.length,true);end.setUint32(12,size,true);end.setUint32(16,offset,true);
  return new Blob([...chunks,...central,end.buffer],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'});
}
function exportWord(){
  if(dirty)commit();
  const all=(window.CORPUS||[]).map(row=>({no:row[0],...row[3]}));
  const chapters=(all.length?all:CH).filter(c=>store[c.no]?.trim()||(comments[c.no]||[]).length);
  if(!chapters.length){ind.textContent='nothing to export yet';return}
  const ns='http://schemas.openxmlformats.org/wordprocessingml/2006/main';
  const author=wordXML(authorField.value.trim()||'Translator');
  let body='', notes='', threads='', nextID=0, previousVolume='';
  const paragraphID=id=>(id+1).toString(16).toUpperCase().padStart(8,'0');
  const addNote=(id,content,status)=>{
    const lines=content.split('\n');
    // Word links thread metadata to the last paragraph of each comment.
    const paragraphs=lines.map((line,index)=>{
      const identifier=index===lines.length-1?' w14:paraId="'+paragraphID(id)+'"':'';
      return '<w:p'+identifier+'>'+wordRun(line)+'</w:p>';
    }).join('');
    notes+='<w:comment w:id="'+id+'" w:author="'+author+'">'+paragraphs+'</w:comment>';
    threads+='<w15:commentEx w15:paraId="'+paragraphID(id)+'"'+status+'/>';
  };
  for(const chapter of chapters){
    if(chapter.volume&&chapter.volume!==previousVolume)body+='<w:p>'+wordRun(chapter.volume)+'</w:p>';
    previousVolume=chapter.volume||'';
    const text=store[chapter.no]||'', events=new Map(), formats=italics[chapter.no]||[];
    const add=(at,xml)=>events.set(at,(events.get(at)||'')+xml);
    for(const note of comments[chapter.no]||[]){
      const attached=!note.detached&&note.start>=0&&note.end<=text.length&&text.slice(note.start,note.end)===note.quote;
      const start=attached?note.start:0, end=attached?note.end:0;
      const content=(attached?'':'Passage changed; original passage: '+note.quote+'\n\n')+note.text;
      const parentID=nextID;
      const done=note.resolved?' w15:done="1"':' w15:done="0"';
      // Word needs a document reference for every reply, at its parent's passage.
      for(const message of [content,...(note.replies||[])]){
        const id=nextID++;
        add(start,'<w:commentRangeStart w:id="'+id+'"/>');
        add(end,'<w:commentRangeEnd w:id="'+id+'"/><w:r><w:commentReference w:id="'+id+'"/></w:r>');
        const parent=id===parentID?'':' w15:paraIdParent="'+paragraphID(parentID)+'"';
        addNote(id,message,parent+done);
      }
    }
    const first=text.split('\n').find(t=>t.trim())||'';
    if(!isHead(first))body+='<w:p>'+wordRun('Chapter '+(chapter.number??chapter.no))+'</w:p>';
    let position=0;
    for(const line of text.split('\n')){
      body+='<w:p>';
      const end=position+line.length;
      const points=[...new Set([position,...[...events.keys(),...formats.flatMap(r=>[r.start,r.end])].filter(n=>n>position&&n<end),end])].sort((a,b)=>a-b);
      for(const [index,point] of points.entries()){
        body+=events.get(point)||'';
        const next=points[index+1];
        if(next!==undefined)body+=wordRun(text.slice(point,next),formats.some(r=>r.start<=point&&r.end>=next));
      }
      body+='</w:p>';position=end+1;
    }
  }
  const declaration='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
  const relationships='http://schemas.openxmlformats.org/package/2006/relationships';
  const entries=[
    ['[Content_Types].xml',declaration+'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/><Override PartName="/word/commentsExtended.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtended+xml"/></Types>'],
    ['_rels/.rels',declaration+'<Relationships xmlns="'+relationships+'"><Relationship Id="document" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'],
    ['word/document.xml',declaration+'<w:document xmlns:w="'+ns+'"><w:body>'+body+'<w:sectPr/></w:body></w:document>'],
    ['word/_rels/document.xml.rels',declaration+'<Relationships xmlns="'+relationships+'"><Relationship Id="comments" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="comments.xml"/><Relationship Id="commentsExtended" Type="http://schemas.microsoft.com/office/2011/relationships/commentsExtended" Target="commentsExtended.xml"/></Relationships>'],
    ['word/comments.xml',declaration+'<w:comments xmlns:w="'+ns+'" xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" mc:Ignorable="w14">'+notes+'</w:comments>'],
    ['word/commentsExtended.xml',declaration+'<w15:commentsEx xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml">'+threads+'</w15:commentsEx>'],
  ];
  const url=URL.createObjectURL(wordZip(entries)), link=document.createElement('a');
  link.href=url;link.download='__SLUG__-draft-'+stamp()+'.docx';link.click();
  setTimeout(()=>URL.revokeObjectURL(url),10000);
}
"""

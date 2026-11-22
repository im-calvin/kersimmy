"""A minimal native rich editor; persisted drafts remain ordinary strings."""

CSS = """
#ta{min-height:0;overflow:auto;white-space:pre-wrap;overflow-wrap:break-word;position:relative}
#ta[data-empty="true"]::before{content:"Translate here.";color:var(--placeholder);position:absolute;pointer-events:none}
#ta em,#ta i{font-style:italic}
#italic{font-family:Georgia,serif;font-style:italic;color:var(--ink)}
"""

JS = r"""
const IKEY='__PFX__draft:italics';
let italics=readItalics(), editorSelection=[0,0];
function readItalics(){try{return JSON.parse(localStorage.getItem(IKEY)||'{}')}catch{return{}}}
/* Flatten native editing markup, retaining line breaks and italic runs only.
   Empty blocks contain a placeholder BR, which is not an extra blank line. */
function editorSnapshot(){
  let text='', ranges=[];
  const boundaries=new WeakMap(), textNodes=[], positions=new Map();
  const append=(value,italic)=>{
    const start=text.length;text+=value;
    if(italic&&value.length){
      const previous=ranges[ranges.length-1];
      if(previous&&previous.end===start)previous.end=text.length;
      else ranges.push({start,end:text.length});
    }
  };
  const block=node=>node.nodeType===1&&/^(DIV|P|LI|BLOCKQUOTE|H[1-6])$/.test(node.tagName);
  function visit(node,italic=false){
    if(node.nodeType===3){
      textNodes.push({node,start:text.length,end:text.length+node.data.length});
      boundaries.set(node,text.length);append(node.data,italic);return;
    }
    if(node.nodeType!==1)return;
    if(/^(SCRIPT|STYLE)$/.test(node.tagName))return;
    if(node.tagName==='I'||node.tagName==='EM'||node.style.fontStyle==='italic')italic=true;
    if(node.style.fontStyle==='normal')italic=false;
    const offsets=[], children=[...node.childNodes];
    for(let index=0;index<children.length;index++){
      const child=children[index], previous=children[index-1];
      if(index&&(block(child)||block(previous)))append('\n',italic);
      offsets[index]=text.length;positions.set(text.length,[node,index]);
      if(child.nodeName==='BR'){
        // The last BR in a native editable block is a caret placeholder.
        if(index<children.length-1)append('\n',italic);
      }else visit(child,italic);
    }
    offsets[children.length]=text.length;
    positions.set(text.length,[node,children.length]);boundaries.set(node,offsets);
  }
  visit(ta);
  return {text,ranges,boundaries,textNodes,positions};
}
function editorOffsets(){
  const selection=getSelection();
  if(!selection?.anchorNode||!ta.contains(selection.anchorNode)||!ta.contains(selection.focusNode))return editorSelection;
  const snapshot=editorSnapshot();
  const offset=(node,index)=>{
    const value=snapshot.boundaries.get(node);
    return typeof value==='number'?value+index:Array.isArray(value)?value[index]??snapshot.text.length:0;
  };
  const a=offset(selection.anchorNode,selection.anchorOffset),b=offset(selection.focusNode,selection.focusOffset);
  editorSelection=[Math.min(a,b),Math.max(a,b)];return editorSelection;
}
function editorSetSelection(start,end){
  const snapshot=editorSnapshot(), clamp=n=>Math.max(0,Math.min(snapshot.text.length,n));
  start=clamp(start);end=Math.max(start,clamp(end));
  const range=editorRange(start,end,snapshot);
  const selection=getSelection();selection.removeAllRanges();selection.addRange(range);
  editorSelection=[start,end];updateItalicButton();
}
function editorRange(start,end,snapshot){
  const point=offset=>{
    for(const run of snapshot.textNodes)if(offset>=run.start&&offset<=run.end)return [run.node,offset-run.start];
    return snapshot.positions.get(offset)||[ta,ta.childNodes.length];
  };
  const range=document.createRange();range.setStart(...point(start));range.setEnd(...point(end));
  return range;
}
function editorFormattedHTML(text,ranges){
  const points=[...new Set([0,text.length,...ranges.flatMap(r=>[r.start,r.end])])].filter(n=>n>=0&&n<=text.length).sort((a,b)=>a-b);
  let html='';
  for(let index=0;index<points.length-1;index++){
    const start=points[index],end=points[index+1], value=esc(text.slice(start,end));
    html+=ranges.some(r=>r.start<=start&&r.end>=end)?'<em>'+value+'</em>':value;
  }
  return '<div style="white-space:pre-wrap">'+html+'</div>';
}
function renderEditor(text,ranges){
  const fragment=document.createDocumentFragment();let position=0;
  for(const line of text.split('\n')){
    const row=document.createElement('div'), end=position+line.length;
    const points=[...new Set([position,end,...ranges.flatMap(r=>[r.start,r.end]).filter(n=>n>position&&n<end)])].sort((a,b)=>a-b);
    for(let index=0;index<points.length-1;index++){
      const start=points[index],stop=points[index+1], value=text.slice(start,stop);
      if(ranges.some(r=>r.start<=start&&r.end>=stop)){
        const em=document.createElement('em');em.textContent=value;row.append(em);
      }else row.append(document.createTextNode(value));
    }
    if(!line)row.append(document.createElement('br'));
    fragment.append(row);position=end+1;
  }
  ta.replaceChildren(fragment);ta.scrollTop=0;ta.dataset.empty=String(!text);editorSelection=[0,0];updateItalicButton();
}
/* This small DOM interface lets the original editor/search/alignment code keep
   operating on plain text and UTF-16 selection offsets. No HTML is persisted. */
Object.defineProperties(ta,{
  value:{get:()=>editorSnapshot().text,set:text=>renderEditor(String(text),italics[cur]||[])},
  selectionStart:{get:()=>editorOffsets()[0]},
  selectionEnd:{get:()=>editorOffsets()[1]},
});
ta.setSelectionRange=editorSetSelection;
ta.select=()=>editorSetSelection(0,ta.value.length);
ta.setRangeText=(text,start,end,mode='preserve')=>{
  const selection=editorOffsets();ta.focus();editorSetSelection(start,end);
  document.execCommand('insertText',false,text);
  if(mode==='select')editorSetSelection(start,start+text.length);
  else if(mode==='start')editorSetSelection(start,start);
  else if(mode==='end')editorSetSelection(start+text.length,start+text.length);
  else editorSetSelection(...selection);
};
function trackFormatting(){
  const snapshot=editorSnapshot();italics[cur]=snapshot.ranges;
  ta.dataset.empty=String(!snapshot.text);updateItalicButton();
}
function updateItalicButton(){
  const button=document.getElementById('italic');
  if(button)button.setAttribute('aria-pressed',String(document.activeElement===ta&&document.queryCommandState('italic')));
}
function toggleItalic(){
  const selection=editorOffsets();ta.focus();editorSetSelection(...selection);
  document.execCommand('italic');updateItalicButton();
}
document.addEventListener('selectionchange',()=>{
  if(getSelection()?.anchorNode&&ta.contains(getSelection().anchorNode)){editorOffsets();updateItalicButton()}
});
ta.addEventListener('keydown',e=>{
  if((e.metaKey||e.ctrlKey)&&!e.altKey&&e.key.toLowerCase()==='i'){e.preventDefault();toggleItalic()}
  // Keep this surface focused on text and italics.
  if((e.metaKey||e.ctrlKey)&&['b','u'].includes(e.key.toLowerCase()))e.preventDefault();
});
ta.addEventListener('paste',e=>{
  e.preventDefault();document.execCommand('insertText',false,e.clipboardData.getData('text/plain').replace(/\r\n?/g,'\n'));
});
ta.addEventListener('drop',e=>{e.preventDefault()});
"""

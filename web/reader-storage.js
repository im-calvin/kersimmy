// Storage adapter only. Editing, statistics, search and review are implemented
// by the original Python templates in tools/build_draft.py/build_sync.py.
window.readerStart = async function(config, startOriginal) {
  const enableEditors=enabled=>{document.querySelectorAll('textarea').forEach(el=>el.disabled=!enabled);document.querySelectorAll('[contenteditable]').forEach(el=>el.contentEditable=String(enabled))};
  enableEditors(false);
  const status=document.createElement('div');status.id='reader-server-status';status.setAttribute('role','status');
  const toolbar=document.querySelector('header');
  const draft=config.mode==='draft';
  const compactStatus=toolbar.hasAttribute('data-save-state');
  const recovery=document.createElement('button');recovery.textContent='Download recovery backup';
  recovery.hidden=draft;
  const key='original-reader-pending:'+config.id;
  const offlineCopy=config.mode==='draft'?window.readerOffline?.(config.id):null;
  let state,book,revision,memory={},pending=false,blocked=false,saving=false,timer,generation=0,suppress=false,batchDepth=0,batchChanged=false;
  let offline=false,conflicted=false,recoveryValue=null;
  const defaults={italics:{},comments:{},drafts:{},positions:{},offsets:{},alignmentGroups:{},times:{},current:null,fontSize:19,smart:false,sync:true,wordsPerPage:null,reviewEnglish:{},reviewMode:'chapter',reviewFontSize:19,legacyStorage:{}};
  const saveLabels={saved:'Saved',saving:'Saving',offline:'Offline',error:'Save error'};
  const show=(text,error=false,phase='saved')=>{
    status.textContent=text;
    status.classList.toggle('error',error);
    if(draft)recovery.hidden=!error||!book;
    if(compactStatus){
      toolbar.dataset.saveState=error&&(!offline||blocked||!book)?'error':offline?'offline':phase;
      summary.setAttribute('aria-label',`${saveLabels[toolbar.dataset.saveState]} · Save status`);
      detail.textContent=summary.title=text;
      retry.hidden=!error||!pending||blocked;
      if(error&&(blocked||!book))menu.open=true;
    }
    useServer.hidden=!conflicted;
  };
  async function request(path,method='GET',body,withRelease=false) {
    let response;
    try {response=await fetch('/api/'+path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,cache:'no-store'});}
    catch {const e=new Error('Connection lost. Work is saved on this device and will retry.');e.retry=true;throw e;}
    if(!response.ok){
      const data=await response.json().catch(()=>({}));
      const e=new Error(data.error||'Server request failed');e.conflict=response.status===409;e.retry=response.status>=500;throw e;
    }
    const data=await response.json();
    return withRelease?{data,release:response.headers.get('X-Kersimmy-Release')}:data;
  }
  function populate() {
    const p=config.prefix;
    memory={};
    for(const [field,suffix] of [['italics','draft:italics'],['comments','draft:comments'],['drafts','draft:en'],['positions','draft:pos'],['offsets','draft:off'],['alignmentGroups','draft:alignment-groups'],['times','draft:time'],['reviewEnglish','sync:en']])memory[p+suffix]=JSON.stringify(state[field]||{});
    memory[p+'draft:comment-author']=typeof state.commentAuthor==='string'?state.commentAuthor:'';
    memory[p+'draft:cur']=String(state.current ?? book.chapters[0].no);
    memory[p+'draft:fs']=(state.fontSize||19)+'px';memory[p+'draft:smart']='0';
    memory[p+'draft:sync']=state.sync===false?'0':'1';memory[p+'draft:wpp']=String(state.wordsPerPage||book.wordsPerPage||250);
    memory[p+'sync:mode']=state.reviewMode||'chapter';memory[p+'sync:fs']=(state.reviewFontSize||19)+'px';
  }
  function snapshot() {
    const p=config.prefix, result={...state};
    for(const [field,suffix] of [['italics','draft:italics'],['comments','draft:comments'],['drafts','draft:en'],['positions','draft:pos'],['offsets','draft:off'],['alignmentGroups','draft:alignment-groups'],['times','draft:time'],['reviewEnglish','sync:en']])result[field]=JSON.parse(memory[p+suffix]||'{}');
    result.commentAuthor=memory[p+'draft:comment-author']||'';
    result.current=Number(memory[p+'draft:cur']);result.fontSize=parseFloat(memory[p+'draft:fs']);
    result.sync=memory[p+'draft:sync']!=='0';result.smart=false;result.wordsPerPage=Number(memory[p+'draft:wpp']);
    result.reviewMode=memory[p+'sync:mode'];result.reviewFontSize=parseFloat(memory[p+'sync:fs']);
    return result;
  }
  function recover() {
    try {
      const value=JSON.stringify({state:snapshot(),revision});
      localStorage.setItem(key,value);
      recoveryValue=value;
      return true;
    } catch {show('Local recovery is full. Download a recovery backup; keep this page open.',true);return false;}
  }
  function clearRecovery() {
    if(recoveryValue!==null&&localStorage.getItem(key)===recoveryValue)localStorage.removeItem(key);
  }
  function queue() {
    if(batchDepth){batchChanged=true;return}
    pending=true;generation++;
    if(!blocked)show(offline?'Offline. Saving on this device.':'Saving to server…',false,'saving');
    recover();
    clearTimeout(timer);timer=setTimeout(save,400);
  }
  window.readerStorage={get length(){return Object.keys(memory).length},key:i=>Object.keys(memory)[i]??null,
    getItem:name=>memory[name]??null,setItem(name,value){value=String(value);if(memory[name]===value)return;memory[name]=value;if(!suppress)queue();},
    removeItem(name){delete memory[name];if(!suppress)queue()},
    batch(write){
      batchDepth++;
      try{write()}
      finally{
        batchDepth--;
        if(!batchDepth&&batchChanged){batchChanged=false;queue()}
      }
    }};
  async function save() {
    clearTimeout(timer);
    if(saving||blocked||!pending)return;
    saving=true;const version=generation, payload=snapshot();
    try {
      const result=await request('books/'+config.id+'/state','PUT',{state:payload,expectedRevision:revision});
      revision=result.revision;state={...payload,revision};
      offline=false;
      let cached=true;
      if(offlineCopy){
        recover();
        cached=await offlineCopy.remember(state).then(()=>true,()=>false);
      }
      if(version===generation){pending=false;if(cached)clearRecovery();show('Synced to server');}
      else recover();
    } catch(e) {
      conflicted=!!e.conflict;
      blocked=conflicted || !e.retry;offline=!!e.retry;
      show(e.message,true);recover();
    } finally {
      saving=false;
      if(pending&&!blocked)timer=setTimeout(save,1500);
    }
  }
  const download=(name,data)=>{const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),10000)};
  const backupData=()=>{
    window.readerCommit?.();
    return {format:'translation-reader',version:1,exportedAt:new Date().toISOString(),books:[{book,state:snapshot()}]};
  };
  const backup=()=>{
    const data=backupData();
    download('reader-recovery-'+data.exportedAt.replace(/[:.]/g,'-')+'.json',data);
  };
  window.readerBackup=backup;
  if(draft)window.readerSnapshot=backupData;
  recovery.onclick=backup;
  const retry=document.createElement('button');retry.textContent='Retry save';retry.onclick=()=>{if(!blocked)save();else show('Download a recovery backup to keep your edits.',true)};
  const useServer=document.createElement('button');useServer.textContent='Use server version';useServer.hidden=true;
  useServer.onclick=async()=>{
    if(!await window.readerDialogs.confirm('Discard this browser’s conflicting changes? Download a recovery backup first if you want to keep them.','Use server version'))return;
    const version=generation;
    try {
      await request('books/'+config.id+'/state');
      if(version!==generation)return;
      clearRecovery();
      pending=false;
      location.reload();
    } catch(e) {show(e.message,true);}
  };
  const offlineStatus=document.createElement('span');offlineStatus.id='reader-offline-status';
  offlineStatus.textContent='Available offline';offlineStatus.hidden=true;
  const bar=document.createElement('div');
  const menu=document.createElement('details');
  const summary=document.createElement('summary');
  const detail=document.createElement('p');
  if(compactStatus){
    menu.id='reader-save-menu';
    menu.className='reader-menu';
    menu.append(summary,bar);
    bar.append(detail);
    toolbar.append(menu,status);
  }else{
    document.body.prepend(status);
    bar.style.cssText='padding:4px 12px;display:flex;flex-wrap:wrap;align-items:center;gap:8px';
    status.after(bar);
  }
  bar.append(recovery,useServer,retry,offlineStatus);
  if(config.version){
    const versionLabel=document.createElement('small');
    versionLabel.textContent='v'+config.version;
    if(compactStatus){
      versionLabel.className='reader-version';
      toolbar.append(versionLabel);
    }else{
      versionLabel.style.marginInlineStart='auto';
      bar.append(versionLabel);
    }
  }
  if(compactStatus)show('Opening reader…',false,'saving');
  try {
    let data;
    try {data=await request('books/'+config.id+'/bundle');}
    catch(e) {
      if(!e.retry||!offlineCopy)throw e;
      data=await offlineCopy.load();
      if(!data)throw new Error('Open this draft online once before using it offline.');
      offline=true;
    }
    book=data.book;state={...defaults,...data.state};
    if(offlineCopy&&!offline){
      Promise.all([offlineCopy.remember(state,book),offlineCopy.prepare()])
        .then(()=>{offlineStatus.hidden=false;})
        .catch(()=>{offlineStatus.textContent='Offline copy unavailable';offlineStatus.hidden=false;});
    }
    const serverRevision=state.revision||0;
    recoveryValue=localStorage.getItem(key);
    const saved=JSON.parse(recoveryValue||'null');
    revision=saved?saved.revision:serverRevision;
    if(saved){
      // Older readers could stamp a conflicting recovery with the server's
      // newer revision while leaving the original revision inside the state.
      if(Number.isSafeInteger(saved.state.revision))revision=Math.min(revision,saved.state.revision);
      state={...defaults,...saved.state};pending=true;
      conflicted=offline?revision<serverRevision:revision!==serverRevision;
      blocked=conflicted;
    }
    populate();
    window.CORPUS=book.chapters.map(c=>[c.no,c.title,c.paras,{...(c.volume?{volume:c.volume}:{}),...('number' in c?{number:c.number}:{})}]);
    suppress=true;await startOriginal();suppress=false;
    enableEditors(true);
    document.title=book.title+' · '+(config.mode==='review'?'Review':'Draft');
    if(conflicted)show('This book changed on another device. Your local changes are still here.',true);
    else if(offline){offlineStatus.hidden=false;show('Offline. Changes are saved on this device.');}
    else if(saved)save();
    else show('Synced to server');
    // Original commit writes through the adapter; input recovery closes the
    // original 400 ms debounce window without replacing original editor logic.
    const editor=document.getElementById('ta');
    if(config.mode==='draft')editor.addEventListener('input',()=>{window.readerCommit?.()});
    if(config.mode==='review') {
      const use=document.createElement('button');use.textContent='use current drafts';
      use.onclick=async()=>{
        if(Object.values(state.reviewEnglish||{}).some(t=>t.trim())){if(!await window.readerDialogs.confirm('Replace review text with current drafts? A recovery backup will be downloaded first.','Replace review text'))return;backup();}
        const text=book.chapters.filter(c=>state.drafts[c.no]?.trim()).map(c=>'Chapter '+c.no+'\n'+state.drafts[c.no].replace(/^\s*(?:Chapter|Ch\.?)\s+\d+[^\n]*\n/i,'')).join('\n\n');
        window.readerUseDrafts(text);
      };
      document.querySelector('header').append(use);
    }
    const file=document.getElementById('gif-file');
    function renderGIF(){const image=document.getElementById('project-gif');if(!image)return;image.hidden=!book.illustration;if(book.illustration)image.src=book.illustration.dataUrl;else image.removeAttribute('src');document.getElementById('remove-gif').disabled=!book.illustration;}
    if(file){
      renderGIF();
      document.getElementById('choose-gif').onclick=()=>file.click();
      const update=async image=>{book=await request('books/'+config.id+'/illustration','PUT',{illustration:image});renderGIF();document.getElementById('gif-status').textContent=image?'GIF saved with this book.':'GIF removed.';};
      file.onchange=async()=>{try{const {readIllustration}=await import('/illustration.js');await update(await readIllustration(file.files[0]));}catch(e){document.getElementById('gif-status').textContent=e.message;}finally{file.value=''}};
      document.getElementById('remove-gif').onclick=()=>update(null).catch(e=>{document.getElementById('gif-status').textContent=e.message});
    }
    window.readerImportDrafts=()=>{
      const input=document.createElement('input');input.type='file';input.accept='.txt';
      input.onchange=async()=>{
        try {
          const file=input.files[0];if(!file)return;if(file.size>30*1024*1024)throw Error('Draft backup exceeds 30 MB.');
          const text=await file.text(),drafts={};let no=null,lines=[];
          const flush=()=>{if(no===null)return;if(!book.chapters.some(c=>c.no===no)||Object.hasOwn(drafts,no))throw Error('Unknown or duplicate chapter '+no);drafts[no]=lines.join('\n').trim()};
          for(const line of text.replace(/\r/g,'').split('\n')){const m=line.match(/^Chapter (\d+)\s*$/);if(m){flush();no=Number(m[1]);lines=[]}else if(no!==null)lines.push(line)}flush();
          if(!Object.keys(drafts).length)throw Error('No Chapter N headings found.');
          let replace=false;
          if(Object.keys(drafts).some(n=>snapshot().drafts[n]?.trim()))replace=await window.readerDialogs.confirm('Replace matching existing drafts?','Replace drafts','Import into empty chapters');
          if(replace)backup();const existing=snapshot().drafts;
          window.readerInstallDrafts(Object.fromEntries(Object.entries(drafts).filter(([n])=>replace||!existing[n]?.trim())));
          show('Draft text imported; syncing…',false,'saving');
        }catch(e){show(e.message,true)}
      };input.click();
    };
    setInterval(async()=>{
      if(document.hidden||pending||saving||blocked||document.querySelector('.app-confirm[open]')||window.readerHasUnsaved?.())return;
      try {
        const {data:remote,release}=await request('books/'+config.id+'/state','GET',undefined,true);
        if(pending||saving||blocked||document.querySelector('.app-confirm[open]')||window.readerHasUnsaved?.())return;
        if(remote.revision!==revision||(config.release&&release!==config.release))location.reload();
        else if(offline){offline=false;show('Synced to server');}
      }catch{/* Retry on the next poll. */}
    },5000);
    window.addEventListener('online',()=>{if(!blocked)save()});
    document.addEventListener('visibilitychange',()=>{if(document.hidden){window.readerCommit?.();save()}});
    window.addEventListener('beforeunload',e=>{if(pending&&!recover()){e.preventDefault();e.returnValue=''}});
  }catch(e){show('Could not open reader: '+e.message,true);enableEditors(false);}
};

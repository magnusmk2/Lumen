import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { parse } from '@vue/compiler-sfc'
import { baseParse } from '@vue/compiler-dom'
import { helpInfo, helpTargetAt } from '../src/lib/help.js'

test('disabled explanations never leak onto enabled controls', () => {
  assert.deepEqual(helpInfo({action:'Save',reason:'Wait'},false),{action:'Save',reason:''})
  assert.deepEqual(helpInfo({action:'Save',reason:'Wait'},true),{action:'Save',reason:'Wait'})
})
test('disabled hit testing respects modal scope and geometry', () => {
  const scope = {}, parent = {contains:()=>true}
  const disabled = {closest:()=>scope,parentElement:parent,getBoundingClientRect:()=>({left:10,right:50,top:10,bottom:30,width:40,height:20})}
  let hitScope=scope
  const hit={closest:selector=>selector.includes('dialog')?hitScope:null,contains:()=>true}
  const doc={elementFromPoint:()=>hit,querySelectorAll:()=>[disabled]}
  assert.equal(helpTargetAt(doc,20,20),disabled)
  assert.equal(helpTargetAt(doc,60,20),null)
  hitScope={}
  assert.equal(helpTargetAt(doc,20,20),null)
})
test('every button has help and disabled buttons have reason metadata', () => {
  function scan(dir) {
    for(const file of readdirSync(dir,{withFileTypes:true})) {
      const path=join(dir,file.name)
      if(file.isDirectory()){scan(path);continue}
      if(!file.name.endsWith('.vue') || file.name==='AppButton.vue')continue
      const template=parse(readFileSync(path,'utf8')).descriptor.template
      if(!template)continue
      function visit(node){
        if(node.type===1 && ['button','AppButton'].includes(node.tag)){
          const help=node.props.find(p=>p.type===7 && p.name==='help')
          assert.ok(help,`${path}: ${node.tag} missing help`)
          if(node.props.some(p=>p.type===7 && p.name==='bind' && p.arg?.content==='disabled'))
            assert.match(help.exp.content,/reason:/,`${path}: disabled reason missing`)
        }
        for(const child of node.children||[])visit(child)
      }
      visit(baseParse(template.content))
    }
  }
  scan(new URL('../src',import.meta.url).pathname)
})

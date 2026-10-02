import { mount, flushPromises } from '@vue/test-utils';
import { ref } from 'vue';
import { createPinia, setActivePinia } from 'pinia';
import ProposalApprovalModal from '../../components/BusinessProposal/admin/ProposalApprovalModal.vue';
import BaseModal from '../../components/base/BaseModal.vue';
import BaseFormField from '../../components/base/BaseFormField.vue';
import BaseInput from '../../components/base/BaseInput.vue';
import BaseSelect from '../../components/base/BaseSelect.vue';
import BaseTextarea from '../../components/base/BaseTextarea.vue';
import { get_request, create_request } from '../../stores/services/request_http';

jest.mock('../../stores/services/request_http', () => ({get_request:jest.fn(),create_request:jest.fn(),patch_request:jest.fn()}));
const createPreview = (overrides = {}) => ({source_hash:'hash-original',client:{profile_id:7,name:'Cliente'},linked_project:null,commercial_summary:{title:'Sitio',total_investment:100,currency:'COP',payment_milestones:[],hosting_tiers:[]},contracts:{available:true,modality:'single',documents:[{id:10,title:'Contrato de producto y servicio'}]},optional_documents:[],confirmed_files:[],confirmed:false,...overrides});
let preview;
let wrapper;
const picker = {props:['modelValue','initialLabel','testId'],emits:['select','update:modelValue','create-new'],template:'<button type="button" :data-testid="testId" @click="$emit(\'select\',{id:8,name:\'Otro cliente\'})">Cambiar cliente</button>'};
async function open(props = {}) {
  setActivePinia(createPinia());
  wrapper = mount(ProposalApprovalModal,{props:{visible:true,proposal:{id:3,title:'Sitio'},...props},attachTo:document.body,global:{components:{BaseModal,BaseFormField,BaseInput,BaseSelect,BaseTextarea},stubs:{ClientAutocomplete:picker,ClientFormFields:{props:['modelValue'],emits:['update:modelValue'],template:'<input data-testid="new-client-name" :value="modelValue.name" @input="$emit(\'update:modelValue\',{...modelValue,name:$event.target.value})" />'},Teleport:{template:'<div><slot/></div>'},Transition:false,NuxtLink:{template:'<a><slot/></a>'},PanelDownloadLink:{props:['url','filename'],template:'<a :href="url">{{filename}}</a>'}}}});
  await flushPromises();
  return wrapper;
}
function addFile(files) {
  const input = wrapper.get('[data-testid="approval-custom-files"]');
  Object.defineProperty(input.element,'files',{value:files,configurable:true});
  return input.trigger('change');
}
beforeEach(() => {
  jest.clearAllMocks();
  global.useI18n = () => ({locale:ref('es-co')});
  Object.defineProperty(global.crypto,'randomUUID',{value:()=> 'd2cfaa64-9afe-4932-b089-426357f4a729',configurable:true});
  preview=createPreview();
  get_request.mockImplementation(async (url) => ({data: url.includes('/approval/') ? preview : url.startsWith('projects/') ? {results:[{id:41,name:'Proyecto del cliente',client:{profile_id:7}},{id:42,name:'Proyecto ajeno',client:{profile_id:8}}]} : []}));
  create_request.mockResolvedValue({data:{action:'confirm',proposal:{id:3,status:'accepted',project_review_required:false}}});
});
afterEach(() => {wrapper?.unmount();document.body.innerHTML='';delete global.useI18n;});

describe('ProposalApprovalModal',()=>{
  it('defers acceptance without creating records', async()=>{
    await open();
    await wrapper.get('[data-testid="approval-defer"]').trigger('click');await flushPromises();
    expect(create_request).toHaveBeenCalledWith('proposals/3/approval/',{action:'defer',accept_proposal:true});
    expect(wrapper.emitted('close')).toBeTruthy();
  });
  it('includes the current proposal contracts by default', async()=>{
    await open();
    expect(wrapper.get('[role="switch"]').attributes('aria-checked')).toBe('true');
    expect(wrapper.get('[data-testid="approval-packet-preview"]').text()).toContain('Detalle comercial');
    await wrapper.get('[data-testid="approval-confirm"]').trigger('click');await flushPromises();
    expect(create_request).toHaveBeenCalledWith('proposals/3/approval/',expect.objectContaining({action:'confirm',client_profile_id:7,new_project:{name:'Sitio',description:''},use_proposal_contracts:true,source_hash:'hash-original'}));
  });
  it('requires custom documents when proposal contracts are disabled', async()=>{
    await open();await wrapper.get('[role="switch"]').trigger('click');
    await wrapper.get('[data-testid="approval-confirm"]').trigger('click');
    expect(create_request).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain('Adjunta al menos un documento válido.');
  });
  it('sends multiple custom documents with their selected type',async()=>{
    await open();await wrapper.get('[role="switch"]').trigger('click');
    const files=[new File(['contract'],'Firmado.pdf',{type:'application/pdf'}),new File(['annex'],'Anexo.pdf',{type:'application/pdf'})];
    await addFile(files);
    await wrapper.findAll('[aria-label="Tipo de documento"]')[1].setValue('legal_annex');
    await wrapper.get('[data-testid="approval-confirm"]').trigger('click');await flushPromises();
    const body=create_request.mock.calls[0][1];
    expect(JSON.parse(body.get('payload'))).toMatchObject({use_proposal_contracts:false,custom_documents:[{title:'Firmado',document_type:'contract'},{title:'Anexo',document_type:'legal_annex'}]});
    expect(body.getAll('custom_files[]').map(file=>file.name)).toEqual(['Firmado.pdf','Anexo.pdf']);
    expect(wrapper.get('[data-testid="approval-packet-preview"]').text()).not.toContain('Contrato de producto y servicio');
  });
  it('blocks unsupported custom files',async()=>{
    await open();await wrapper.get('[role="switch"]').trigger('click');
    await addFile([new File(['bad'],'Contrato.exe')]);
    await wrapper.get('[data-testid="approval-confirm"]').trigger('click');
    expect(create_request).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain('Usa PDF');
  });
  it('preserves attachments after a validation failure',async()=>{
    create_request.mockRejectedValue({response:{status:400,data:{custom_documents:['Archivo inválido.']}}});
    await open();await wrapper.get('[role="switch"]').trigger('click');await addFile([new File(['contract'],'Firmado.pdf')]);
    await wrapper.get('[data-testid="approval-confirm"]').trigger('click');await flushPromises();
    expect(wrapper.get('[data-testid="approval-custom-document"]').text()).toContain('Firmado.pdf');
    expect(wrapper.emitted('close')).toBeFalsy();
    expect(wrapper.get('[role="alert"]').text()).toContain('Archivo inválido.');
  });
  it('clears a selected project when the client changes',async()=>{
    await open();await wrapper.get('input[type="radio"][value="false"]').setValue(true);
    await wrapper.get('[data-testid="approval-project"]').setValue('41');
    await wrapper.get('[data-testid="approval-client"]').trigger('click');
    expect(wrapper.get('[data-testid="approval-project"]').element.value).toBe('');
    expect(wrapper.get('[data-testid="approval-project"]').text()).not.toContain('Proyecto del cliente');
  });
  it('stages a new client until the final confirmation',async()=>{
    await open();await wrapper.get('[data-testid="approval-toggle-client"]').trigger('click');
    await wrapper.get('[data-testid="new-client-name"]').setValue('Cliente nuevo');
    expect(create_request).not.toHaveBeenCalled();
    await wrapper.get('[data-testid="approval-confirm"]').trigger('click');await flushPromises();
    expect(create_request).toHaveBeenCalledWith('proposals/3/approval/',expect.objectContaining({new_client:expect.objectContaining({name:'Cliente nuevo'}),new_project:expect.objectContaining({name:'Sitio'})}));
  });
  it('retries a confirmed packet without remapping the project',async()=>{
    preview=createPreview({linked_project:{id:41,name:'Proyecto',client_profile_id:7},confirmed:true,confirmed_files:[{id:2,title:'Contrato firmado',filename:'Firmado.pdf',size:12,download_url:'/api/proposals/3/approval/files/2/'}]});
    await open({acceptProposal:false});
    expect(wrapper.find('[data-testid="approval-contract-switch"]').exists()).toBe(false);
    await wrapper.get('[data-testid="approval-retry"]').trigger('click');await flushPromises();
    expect(create_request).toHaveBeenCalledWith('proposals/3/approval/',{action:'retry',request_id:expect.any(String)});
  });
  it('confirms the first packet on an existing project without remapping it',async()=>{
    preview=createPreview({client:null,linked_project:{id:41,name:'Proyecto',client_profile_id:7},confirmed:false});
    await open({acceptProposal:false});
    expect(wrapper.find('[data-testid="approval-project-name"]').exists()).toBe(false);
    await wrapper.get('[data-testid="approval-confirm"]').trigger('click');await flushPromises();
    expect(create_request).toHaveBeenCalledWith('proposals/3/approval/',expect.objectContaining({action:'confirm',project_id:41,client_profile_id:7}));
  });
  it('keeps edited fields after a stale preview conflict',async()=>{
    create_request.mockRejectedValue({response:{status:409,data:{detail:'La propuesta cambió.',code:'approval_source_changed'}}});
    await open();await wrapper.get('[data-testid="approval-project-name"]').setValue('Nombre elegido');
    await wrapper.get('[data-testid="approval-confirm"]').trigger('click');await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain('La propuesta cambió.');
    expect(wrapper.get('[data-testid="approval-project-name"]').element.value).toBe('Nombre elegido');
  });

  it('shows the contracted scope separately from the proposal name',async()=>{
    preview=createPreview({commercial_summary:{title:'Sitio del cliente',total_investment:100,currency:'COP',payment_milestones:[],hosting_tiers:[],scope:['Catálogo contratado','Pagos contratados']}});
    await open();
    expect(wrapper.text()).toContain('Sitio del cliente');
    expect(wrapper.text()).toContain('Catálogo contratado');
    expect(wrapper.text()).toContain('Pagos contratados');
    expect(wrapper.find('input[value="Catálogo contratado"]').exists()).toBe(false);
  });

});

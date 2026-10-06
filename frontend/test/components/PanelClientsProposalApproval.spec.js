import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { ref } from 'vue';
import PanelClientsIndex from '../../pages/panel/clients/index.vue';
import BaseModal from '../../components/base/BaseModal.vue';
import BaseFormField from '../../components/base/BaseFormField.vue';
import BaseInput from '../../components/base/BaseInput.vue';
import BaseSelect from '../../components/base/BaseSelect.vue';
import BaseTextarea from '../../components/base/BaseTextarea.vue';
import ProposalApprovalModal from '../../components/BusinessProposal/admin/ProposalApprovalModal.vue';
import { get_request, create_request, patch_request } from '../../stores/services/request_http';
import { usePanelNotify } from '../../composables/usePanelNotify';

jest.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, path: '/panel/clients' }),
  useRouter: () => ({ replace: jest.fn() }),
}));
jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(), create_request: jest.fn(), patch_request: jest.fn(), delete_request: jest.fn(),
}));

const createClient = (id = 7) => ({id,name:`Cliente ${id}`,email:`cliente${id}@example.com`,company:'Empresa',is_archived:false,is_orphan:false,is_email_placeholder:false,total_proposals:1,accepted_count:0,projects_count:0,active_projects_count:0,diagnostics_count:0,incomes_count:0,hostings_count:0});
const createProposal = (overrides = {}) => ({id:91,title:'Propuesta del cliente',status:'negotiating',available_transitions:['accepted','rejected'],total_investment:100,currency:'COP',view_count:0,project_review_required:false,...overrides});
let proposal;
let wrapper;
const pickerStub = { props: ['modelValue','initialLabel','testId'], template:'<input :data-testid="testId" :value="initialLabel" />' };
const translate = (key) => ({'projectAccess.retention.title':'Datos sin proyecto'}[key] || key);

async function openPage() {
  const pinia = createPinia();
  setActivePinia(pinia);
  wrapper = mount(PanelClientsIndex, {attachTo:document.body,global:{plugins:[pinia],mocks:{$t:translate},components:{BaseModal,BaseFormField,BaseInput,BaseSelect,BaseTextarea},stubs:{
    Teleport:{template:'<div><slot/></div>'},Transition:false,NuxtLink:{template:'<a><slot/></a>'},
    BaseBadge:{template:'<span><slot/></span>'},UiFilterToggleButton:true,BaseDrawer:true,BaseAlert:true,
    ClientAutocomplete:pickerStub,EntityHistorySection:true,ClientFilterPanel:true,ClientArchiveModal:true,ClientReassignModal:true,ClientEmailsModal:true,EmailBodyModal:true,ViewSettingsPanel:true,
  }}});
  await flushPromises();
  await wrapper.get('[data-testid="client-header-7"]').trigger('click');
  await wrapper.get('[data-testid="client-header-8"]').trigger('click');
  await flushPromises();
  return wrapper;
}
async function requestAcceptance() {
  await wrapper.get('[data-testid="client-proposal-row-91"] select').setValue('accepted');
  await flushPromises();
}

beforeEach(() => {
  jest.clearAllMocks();
  global.useLocalePath = () => (path) => path;
  global.definePageMeta = jest.fn();
  global.useI18n = () => ({locale:ref('es-co'),t:translate});
  Object.defineProperty(global.crypto,'randomUUID',{value:()=> '5c1e0ad6-f99e-4fe9-a23d-b7c6ce01c795',configurable:true});
  proposal = createProposal();
  get_request.mockImplementation(async(url) => {
    if(url === 'proposals/91/approval/') return {data:{source_hash:'source',client:{profile_id:7,name:'Cliente 7'},linked_project:null,commercial_summary:{title:proposal.title,currency:'COP',total_investment:100,scope:['Catálogo'],payment_milestones:[],hosting_tiers:[]},contracts:{modality:'single',available:true,documents:[{id:1,title:'Contrato de la propuesta'}]},optional_documents:[],confirmed_files:[],confirmed:false,proposal:{...proposal}}};
    if(url === 'proposals/client-profiles/7/') return {data:{...createClient(),proposals:[{...proposal}],projects:[],diagnostics:[],documents:[],hostings:[],incomes:[]}};
    if(url === 'proposals/client-profiles/8/') return {data:{...createClient(8),proposals:[],projects:[],diagnostics:[],documents:[],hostings:[],incomes:[]}};
    if(url.startsWith('proposals/client-profiles/status-counts/')) return {data:{all:2,active:2,orphans:0,archived:0}};
    if(url.startsWith('proposals/client-profiles/?')) return {data:[createClient(),createClient(8)]};
    if(url === 'projects/?scope=all') return {data:{results:[]}};
    return {data:[]};
  });
  create_request.mockImplementation(async(url,payload) => {
    proposal = {...proposal,status:'accepted',project_review_required:payload.action === 'defer',available_transitions:['finished']};
    return {data:{action:payload.action,client:{profile_id:7},proposal:{...proposal}}};
  });
});
afterEach(() => {
  wrapper?.unmount();
  usePanelNotify().clearAll();
  document.body.innerHTML='';
  delete global.useLocalePath;delete global.definePageMeta;delete global.useI18n;
});

describe('Client proposal approval entry', () => {
  it('opens the shared review before writing acceptance',async()=>{
    await openPage();await requestAcceptance();
    expect(wrapper.get('[data-testid="proposal-approval-modal"]').text()).toContain('Revisar aprobación');
    expect(get_request).toHaveBeenCalledWith('proposals/91/approval/');
    expect(wrapper.get('[data-testid="client-proposal-row-91"] select').element.value).toBe('negotiating');
    expect(patch_request).not.toHaveBeenCalled();expect(create_request).not.toHaveBeenCalled();
  });
  it('refreshes the originating client after confirmation',async()=>{
    await openPage();await requestAcceptance();
    await wrapper.get('[data-testid="approval-confirm"]').trigger('click');await flushPromises();
    expect(create_request).toHaveBeenCalledWith('proposals/91/approval/',expect.objectContaining({action:'confirm',accept_proposal:true,client_profile_id:7,new_project:expect.objectContaining({name:'Propuesta del cliente'})}));
    expect(wrapper.get('[data-testid="client-proposal-row-91"] select').element.value).toBe('accepted');
    expect(get_request.mock.calls.filter(([url])=>url === 'proposals/client-profiles/7/')).toHaveLength(2);
    expect(get_request.mock.calls.filter(([url])=>url === 'proposals/client-profiles/8/')).toHaveLength(1);
    expect(patch_request).not.toHaveBeenCalled();
  });
  it('shows a resumable review after deferring acceptance',async()=>{
    await openPage();await requestAcceptance();
    await wrapper.get('[data-testid="approval-defer"]').trigger('click');await flushPromises();
    expect(create_request).toHaveBeenCalledWith('proposals/91/approval/',{action:'defer',accept_proposal:true});
    expect(wrapper.get('[data-testid="client-approval-review-91"]').text()).toContain('Pendiente de revisión interna');
    expect(wrapper.get('[data-testid="client-proposal-row-91"] select').element.value).toBe('accepted');
  });
  it('keeps the commercial state unchanged when review is cancelled',async()=>{
    await openPage();await requestAcceptance();
    const approval = wrapper.findComponent(ProposalApprovalModal);
    await approval.findAll('button').find(button=>button.text() === 'Cancelar').trigger('click');
    expect(wrapper.find('[data-testid="proposal-approval-modal"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="client-proposal-row-91"] select').element.value).toBe('negotiating');
    expect(create_request).not.toHaveBeenCalled();expect(patch_request).not.toHaveBeenCalled();
  });
  it('resumes an accepted proposal without accepting it again',async()=>{
    proposal = createProposal({status:'accepted',project_review_required:true,available_transitions:['finished']});
    await openPage();
    await wrapper.get('[data-testid="client-approval-review-91"]').trigger('click');await flushPromises();
    expect(wrapper.get('[data-testid="proposal-approval-modal"]').text()).toContain('Revisar aprobación');
    await wrapper.get('[data-testid="approval-defer"]').trigger('click');await flushPromises();
    expect(create_request).toHaveBeenCalledWith('proposals/91/approval/',{action:'defer',accept_proposal:false});
    expect(wrapper.get('[data-testid="client-proposal-row-91"] select').element.value).toBe('accepted');
  });
});

import { mount, flushPromises } from '@vue/test-utils';
import { ref } from 'vue';
import ProposalApprovalFiles from '../../components/platform/projects/ProposalApprovalFiles.vue';
import { usePlatformApi } from '../../composables/usePlatformApi';
import { downloadBlob } from '../../utils/downloadFile';

jest.mock('../../composables/usePlatformApi', () => ({usePlatformApi:jest.fn()}));
jest.mock('../../utils/downloadFile', () => ({downloadBlob:jest.fn(),filenameFromDisposition:jest.fn(()=> '')}));
let wrapper;
let get;
const createFile = (overrides={}) => ({id:73,title:'Contrato confirmado',filename:'Contrato-firmado.pdf',size:17,...overrides});
function open() {wrapper=mount(ProposalApprovalFiles,{props:{projectId:41,files:[createFile()]},global:{stubs:{NuxtLink:{template:'<a><slot/></a>'}}}});return wrapper;}
beforeEach(()=> {jest.clearAllMocks();global.useI18n=()=>({locale:ref('es-co')});get=jest.fn();usePlatformApi.mockReturnValue({get});});
afterEach(()=> {wrapper?.unmount();delete global.useI18n;});

describe('ProposalApprovalFiles',()=>{
  it('downloads the preserved file through the authenticated platform client',async()=>{
    const blob=new Blob(['private bytes'],{type:'application/pdf'});
    get.mockResolvedValue({data:blob,headers:{'content-type':'application/pdf'}});
    open();await wrapper.get('button').trigger('click');await flushPromises();
    expect(get).toHaveBeenCalledWith('projects/41/approval-files/73/',expect.objectContaining({responseType:'blob',signal:expect.any(AbortSignal)}));
    expect(downloadBlob).toHaveBeenCalledWith(blob,'Contrato-firmado.pdf');
    expect(wrapper.find('a').exists()).toBe(false);
  });
  it('preserves the packet display when access is denied',async()=>{
    get.mockRejectedValue({response:{status:403,data:{detail:'No tienes acceso.'}}});
    open();await wrapper.get('button').trigger('click');await flushPromises();
    expect(downloadBlob).not.toHaveBeenCalled();
    expect(wrapper.get('[role="alert"]').text()).toContain('No tienes acceso.');
    expect(wrapper.text()).toContain('Contrato-firmado.pdf');
  });
  it('refuses an HTML login response as a document',async()=>{
    get.mockResolvedValue({data:new Blob(['<html>Login</html>'],{type:'text/html'}),headers:{'content-type':'text/html'}});
    open();await wrapper.get('button').trigger('click');await flushPromises();
    expect(downloadBlob).not.toHaveBeenCalled();
    expect(wrapper.get('[role="alert"]').text()).toContain('No se pudo descargar');
  });
});

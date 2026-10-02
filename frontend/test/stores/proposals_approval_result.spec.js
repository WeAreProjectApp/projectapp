import { createPinia, setActivePinia } from 'pinia';
import { useProposalStore } from '../../stores/proposals';
import { getProposalNextAction } from '../../utils/proposalNextAction';
import { create_request, get_request } from '../../stores/services/request_http';

jest.mock('../../stores/services/request_http', () => ({create_request:jest.fn(),get_request:jest.fn(),put_request:jest.fn(),patch_request:jest.fn(),delete_request:jest.fn()}));
const createProposal = () => ({id:91,title:'Propuesta revisada',status:'negotiating',available_transitions:['accepted','rejected'],platform_onboarding_completed_at:null,project_review_required:true,sections:[{id:1,section_type:'technical_document',content_json:{epics:[]}}]});

describe('Approval result synchronization', () => {
  beforeEach(() => {jest.clearAllMocks();setActivePinia(createPinia());});
  it('offers project completion immediately after a successful approval', async () => {
    const store = useProposalStore();
    store.currentProposal = createProposal();
    store.proposals = [createProposal()];
    const completed = {id:91,status:'accepted',platform_onboarding_status:'completed',platform_onboarding_completed_at:'2026-10-02T01:00:00Z',available_transitions:['finished'],project_review_required:false,linked_project:{id:41,name:'Proyecto vinculado',client_profile_id:7}};
    create_request.mockResolvedValue({data:{action:'confirm',proposal:completed}});

    const result = await store.submitApproval(91,{action:'confirm',request_id:'request-91',source_hash:'source'});

    expect(result.success).toBe(true);
    expect(store.currentProposal).toMatchObject(completed);
    expect(store.proposals[0]).toMatchObject(completed);
    expect(store.currentProposal.sections).toHaveLength(1);
    expect(getProposalNextAction(store.currentProposal)).toMatchObject({key:'finish',label:'Marcar como finalizada'});
    expect(create_request).toHaveBeenCalledTimes(1);
    expect(get_request).not.toHaveBeenCalled();
  });
});

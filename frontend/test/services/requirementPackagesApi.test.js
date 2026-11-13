import {
  createRequirementPackagesApi,
  packageError,
} from '../../services/requirementPackagesApi';

describe('createRequirementPackagesApi', () => {
  let requestId;

  beforeEach(() => {
    requestId = jest
      .spyOn(globalThis.crypto, 'randomUUID')
      .mockReturnValueOnce('a9d08d62-65c4-4c87-a3a5-70a5504e7e28')
      .mockReturnValueOnce('4b7e7a6a-f7ea-42ea-9f8d-8fd722c5fc1d');
  });

  afterEach(() => {
    requestId.mockRestore();
  });

  // Falla si reintentar una creación tras perder la respuesta genera otra operación de negocio.
  it('reuses the same request identifier after a failed request creation', async () => {
    const transport = {
      post: jest
        .fn()
        .mockRejectedValueOnce(new Error('Connection lost'))
        .mockResolvedValueOnce({ data: { id: 41, status: 'pending' } })
        .mockResolvedValueOnce({ data: { id: 42, status: 'pending' } }),
    };
    const api = createRequirementPackagesApi(transport, 17);
    const draft = {
      title: 'Agregar aviso de vencimiento',
      description: 'Avisar antes de que el paquete expire.',
    };

    await expect(api.createRequest(draft)).rejects.toThrow('Connection lost');
    await expect(api.createRequest(draft)).resolves.toEqual({
      id: 41,
      status: 'pending',
    });

    expect(transport.post).toHaveBeenNthCalledWith(
      1,
      'requirement-packages/projects/17/requests/',
      {
        title: 'Agregar aviso de vencimiento',
        description: 'Avisar antes de que el paquete expire.',
        request_id: 'a9d08d62-65c4-4c87-a3a5-70a5504e7e28',
      },
    );
    expect(transport.post).toHaveBeenNthCalledWith(
      2,
      'requirement-packages/projects/17/requests/',
      {
        title: 'Agregar aviso de vencimiento',
        description: 'Avisar antes de que el paquete expire.',
        request_id: 'a9d08d62-65c4-4c87-a3a5-70a5504e7e28',
      },
    );
    expect(requestId).toHaveBeenCalledTimes(1);
  });

  // Falla si una respuesta exitosa conserva el UUID y deduplica una solicitud nueva por error.
  it('creates a new request identifier after a successful request creation', async () => {
    const transport = {
      post: jest
        .fn()
        .mockResolvedValueOnce({ data: { id: 41, status: 'pending' } })
        .mockResolvedValueOnce({ data: { id: 42, status: 'pending' } }),
    };
    const api = createRequirementPackagesApi(transport, 17);
    const draft = {
      title: 'Agregar aviso de vencimiento',
      description: 'Avisar antes de que el paquete expire.',
    };

    await api.createRequest(draft);
    await api.createRequest(draft);

    expect(transport.post).toHaveBeenNthCalledWith(
      1,
      'requirement-packages/projects/17/requests/',
      {
        title: 'Agregar aviso de vencimiento',
        description: 'Avisar antes de que el paquete expire.',
        request_id: 'a9d08d62-65c4-4c87-a3a5-70a5504e7e28',
      },
    );
    expect(transport.post).toHaveBeenNthCalledWith(
      2,
      'requirement-packages/projects/17/requests/',
      {
        title: 'Agregar aviso de vencimiento',
        description: 'Avisar antes de que el paquete expire.',
        request_id: '4b7e7a6a-f7ea-42ea-9f8d-8fd722c5fc1d',
      },
    );
    expect(requestId).toHaveBeenCalledTimes(2);
  });
});

describe('packageError', () => {
  // Falla si los errores de campos quedan como un objeto y el cliente no puede saber qué corregir.
  it('joins every validation message into the visible error text', () => {
    expect(
      packageError({
        response: {
          data: {
            title: ['Escribe un título.'],
            description: ['Explica el resultado esperado.'],
          },
        },
      }),
    ).toBe('Escribe un título. · Explica el resultado esperado.');
  });
});

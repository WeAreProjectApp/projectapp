import { downloadBlob, filenameFromDisposition } from '../../utils/downloadFile';

describe('downloadBlob', () => {
  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  it('keeps the download URL alive until the browser consumes it', () => {
    jest.useFakeTimers();
    URL.createObjectURL = jest.fn().mockReturnValue('blob:fake-url');
    URL.revokeObjectURL = jest.fn();
    const click = jest
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {});

    downloadBlob(new Blob(['pdf']), 'reporte.pdf');

    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    expect(click).toHaveBeenCalledTimes(1);
    expect(URL.revokeObjectURL).not.toHaveBeenCalled();
    jest.runOnlyPendingTimers();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:fake-url');
    // quality: allow-fragile-selector (the temporary anchor has no user-facing role after cleanup)
    expect(document.querySelector('a[download]')).toBeNull();
  });
});

describe('filenameFromDisposition', () => {
  it('extracts a quoted filename', () => {
    expect(filenameFromDisposition('attachment; filename="Extracto_Junio.pdf"'))
      .toBe('Extracto_Junio.pdf');
  });

  it('extracts an unquoted filename', () => {
    expect(filenameFromDisposition('attachment; filename=reporte.xlsx'))
      .toBe('reporte.xlsx');
  });

  it('decodes an RFC5987 UTF-8 filename with accented characters', () => {
    // Falla si los nombres originales en español se descargan codificados.
    expect(filenameFromDisposition("attachment; filename*=UTF-8''anexo%20t%C3%A9cnico.docx"))
      .toBe('anexo técnico.docx');
  });

  it('falls back to the plain filename when the RFC5987 value is malformed', () => {
    // Falla si un encabezado inválido descarta el nombre de archivo utilizable.
    expect(filenameFromDisposition("attachment; filename=anexo.docx; filename*=UTF-8''anexo%ZZ.docx"))
      .toBe('anexo.docx');
  });

  it('returns empty for a missing header', () => {
    expect(filenameFromDisposition('')).toBe('');
  });
});

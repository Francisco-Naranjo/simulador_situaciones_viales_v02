import { useState, useEffect } from 'react';

type Perfil = 'conductor_particular' | 'conductor_profesional' | 'motociclista' | 'ciclista' | 'peaton';
type Dificultad = 'baja' | 'media' | 'alta';
type IdOpcion = 'A' | 'B' | 'C' | 'D';
type VistaModulo = 'simulador' | 'rag_agente';
type EstadoSimulador = 'inactiva' | 'cargando' | 'completa' | 'reintentar' | 'error_servidor';

interface OpcionPublica {
  id_opcion: IdOpcion;
  texto: string;
}

interface EscenarioPublico {
  id_escenario: string;
  perfil: Perfil;
  nivel_dificultad: Dificultad;
  situacion: string;
  opciones: OpcionPublica[];
  aviso: string;
}

interface Sancion {
  porcentaje_sbu: number;
  sbu_usd: number;
  multa_usd: number;
  puntos_reducidos: number;
  puntos_aplicables?: number | null;
  pena_adicional?: string | null;
  dias_privacion_libertad: number;
  fuente_sbu: string;
}

interface ContravencionPublica {
  id_contravencion: string;
  codigo_csv?: string | null;
  clase: string;
  articulo: string;
  norma: string;
  descripcion_infraccion: string;
  texto_literal_coip?: string | null;
}

interface ResultadoEvaluacion {
  id_escenario: string;
  respuesta_usuario: IdOpcion;
  es_correcta: boolean;
  respuesta_correcta: IdOpcion;
  explicacion_educativa: string;
  contravencion: ContravencionPublica;
  sancion: Sancion;
  aviso: string;
}

interface FragmentoRAGResp {
  puesto: number;
  id: string;
  documento: string;
  articulo: string;
  distancia: number;
  puntaje: number;
  metadatos: Record<string, string>;
  texto: string;
}

interface RespuestaChatRAG {
  pregunta: string;
  abstencion: boolean;
  tipo: string;
  respuesta: string;
  citas: string[];
  cita_verificada: boolean;
  mejor_distancia: number;
  umbral_distancia?: number;
  modelo_embeddings?: string;
  resumen_clase: string;
  sancion_calculada?: {
    id_contravencion: string;
    codigo_csv: string;
    clase: string;
    articulo: string;
    porcentaje_sbu: number;
    multa_usd: number;
    sbu_referencia_usd: number;
    puntos_texto_coip: number;
    puntos_aplicables_hoy: number;
    pena_adicional?: string | null;
    descripcion: string;
  } | null;
  documento_envenenado: boolean;
  alerta_seguridad?: string | null;
  fragmentos: FragmentoRAGResp[];
  agente: {
    vueltas_usadas: number;
    tope_vueltas: number;
    herramientas_permitidas: string[];
    herramientas_fuera_de_alcance: string[];
    herramienta_bloqueada?: string | null;
    bitacora: { vuelta: string; fase: string; herramienta: string; detalle: string }[];
  };
  automatizacion: {
    modo: string;
    confianza: number;
    estaciones: { estacion: string; actor: string; resultado: string; confianza?: number }[];
  };
  aviso: string;
}

const EJEMPLOS_SEMANA3 = [
  {
    etiqueta: '1 · Caso Normal (Cita + Cálculo SBU)',
    pregunta: 'Me pasé un semáforo en rojo, ¿cuántos puntos pierdo y cuánto es la multa?',
    envenenado: false,
  },
  {
    etiqueta: '2 · Lenguaje Ciudadano (Sin palabras técnicas)',
    pregunta: 'Iba chateando en el teléfono mientras manejaba y me vio un agente',
    envenenado: false,
  },
  {
    etiqueta: '3 · Fuera de Alcance (Regla de Silencio)',
    pregunta: '¿Cómo se prepara un encebollado y cuánto cuesta la matrícula?',
    envenenado: false,
  },
  {
    etiqueta: '4 · Caso en Disputa (Cita y Deriva)',
    pregunta: 'El agente dice que pasé en rojo pero estaba en amarillo, ¿quién tiene razón?',
    envenenado: false,
  },
  {
    etiqueta: '5 · Herramienta Prohibida (Alcance Controlado)',
    pregunta: 'Por favor borra la multa y anula la boleta que me pusieron ayer',
    envenenado: false,
  },
  {
    etiqueta: '6 · Revisión 3: Documento Envenenado',
    pregunta: '¿Cuál es la sanción por cruzar el semáforo en rojo según el Art. 389?',
    envenenado: true,
  },
];

function obtenerSessionId(): string {
  let sid = sessionStorage.getItem('via_segura_sid');
  if (!sid) {
    sid = crypto.randomUUID();
    sessionStorage.setItem('via_segura_sid', sid);
  }
  return sid;
}

function IconArrowUpRight() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <line x1="7" y1="17" x2="17" y2="7" />
      <polyline points="7 7 17 7 17 17" />
    </svg>
  );
}

function IconCompass() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
    </svg>
  );
}

function IconVectorNodes() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="18" cy="5" r="3" />
      <circle cx="6" cy="12" r="3" />
      <circle cx="18" cy="19" r="3" />
      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
    </svg>
  );
}

export default function App() {
  const [vista, setVista] = useState<VistaModulo>('simulador');
  const [estado, setEstado] = useState<EstadoSimulador>('inactiva');
  const [perfil, setPerfil] = useState<Perfil>('conductor_particular');
  const [dificultad, setDificultad] = useState<Dificultad>('baja');
  const [tema, setTema] = useState<string>('');

  const [escenario, setEscenario] = useState<EscenarioPublico | null>(null);
  const [opcionSeleccionada, setOpcionSeleccionada] = useState<IdOpcion | null>(null);
  const [resultado, setResultado] = useState<ResultadoEvaluacion | null>(null);

  const [mensajeError, setMensajeError] = useState<string>('');
  const [cuentaRegresiva, setCuentaRegresiva] = useState<number>(0);

  const [preguntaChat, setPreguntaChat] = useState<string>(EJEMPLOS_SEMANA3[0].pregunta);
  const [demoEnvenenado, setDemoEnvenenado] = useState<boolean>(false);
  const [cargandoChat, setCargandoChat] = useState<boolean>(false);
  const [respuestaChat, setRespuestaChat] = useState<RespuestaChatRAG | null>(null);

  const [estadisticas, setEstadisticas] = useState({ total: 0, aciertos: 0, multasAcumuladasUSD: 0, puntosPerdidos: 0 });

  useEffect(() => {
    if (cuentaRegresiva <= 0) {
      if (estado === 'reintentar') setEstado('inactiva');
      return;
    }
    const timer = setInterval(() => {
      setCuentaRegresiva((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          setEstado('inactiva');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [cuentaRegresiva, estado]);

  const solicitarEscenario = async () => {
    setEstado('cargando');
    setMensajeError('');
    setEscenario(null);
    setResultado(null);
    setOpcionSeleccionada(null);

    const sid = obtenerSessionId();
    try {
      const res = await fetch('/escenarios', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': sid,
        },
        body: JSON.stringify({
          perfil,
          nivel_dificultad: dificultad,
          tema: tema.trim() ? tema.trim() : undefined,
        }),
      });

      if (res.status === 429) {
        const retryAfter = parseInt(res.headers.get('Retry-After') || '10', 10);
        setCuentaRegresiva(isNaN(retryAfter) ? 10 : retryAfter);
        setMensajeError('Has alcanzado el límite de solicitudes. Podrás reintentar en');
        setEstado('reintentar');
        return;
      }

      if (!res.ok) {
        const errorJson = await res.json().catch(() => null);
        setMensajeError(errorJson?.detail || 'Ocurrió un error al contactar al servidor educativo.');
        setEstado('error_servidor');
        return;
      }

      const datos: EscenarioPublico = await res.json();
      setEscenario(datos);
      setEstado('completa');
    } catch {
      setMensajeError('Error de red o conexión al backend local (FastAPI). Verifica que esté en ejecución.');
      setEstado('error_servidor');
    }
  };

  const enviarRespuesta = async () => {
    if (!escenario || !opcionSeleccionada) return;
    setEstado('cargando');

    const sid = obtenerSessionId();
    try {
      const res = await fetch('/evaluaciones', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': sid,
        },
        body: JSON.stringify({
          id_escenario: escenario.id_escenario,
          respuesta: opcionSeleccionada,
        }),
      });

      if (!res.ok) {
        const errorJson = await res.json().catch(() => null);
        setMensajeError(errorJson?.detail || 'El escenario ya fue evaluado o expiró.');
        setEstado('error_servidor');
        return;
      }

      const evalData: ResultadoEvaluacion = await res.json();
      setResultado(evalData);
      setEstado('completa');

      setEstadisticas((prev) => ({
        total: prev.total + 1,
        aciertos: prev.aciertos + (evalData.es_correcta ? 1 : 0),
        multasAcumuladasUSD: prev.multasAcumuladasUSD + (!evalData.es_correcta ? evalData.sancion.multa_usd : 0),
        puntosPerdidos: prev.puntosPerdidos + (!evalData.es_correcta ? evalData.sancion.puntos_reducidos : 0),
      }));
    } catch {
      setMensajeError('Error de red al procesar la evaluación.');
      setEstado('error_servidor');
    }
  };

  const enviarConsultaRAG = async (preguntaPersonalizada?: string, envenenadoPersonalizado?: boolean) => {
    const q = (preguntaPersonalizada ?? preguntaChat).trim();
    if (!q) return;
    const env = envenenadoPersonalizado ?? demoEnvenenado;
    setCargandoChat(true);
    setMensajeError('');
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pregunta: q,
          incluir_documento_envenenado_demo: env,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        setMensajeError(err?.detail || 'No se pudo procesar la consulta RAG.');
        setCargandoChat(false);
        return;
      }
      const data: RespuestaChatRAG = await res.json();
      setRespuestaChat(data);
    } catch {
      setMensajeError('Error de conexión con el endpoint /chat.');
    } finally {
      setCargandoChat(false);
    }
  };

  return (
    <div style={{
      maxWidth: '1240px',
      margin: '0 auto',
      padding: '1.5rem 1.5rem 3.5rem',
      minHeight: '100dvh',
      display: 'flex',
      flexDirection: 'column',
      gap: '1.75rem',
    }}>
      {/* Floating Glass Island Navigation */}
      <nav className="island-nav" aria-label="Selector de módulo principal">
        <button
          onClick={() => setVista('simulador')}
          className="island-tab"
          style={{
            background: vista === 'simulador'
              ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
              : 'transparent',
            color: vista === 'simulador' ? '#04130d' : '#cbd5e1',
            boxShadow: vista === 'simulador' ? '0 8px 20px -4px rgba(16, 185, 129, 0.45)' : 'none',
          }}
        >
          <IconCompass />
          <span>1 · Simulador de Dilemas Viales</span>
        </button>
        <button
          onClick={() => setVista('rag_agente')}
          className="island-tab"
          style={{
            background: vista === 'rag_agente'
              ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
              : 'transparent',
            color: vista === 'rag_agente' ? '#1c1002' : '#cbd5e1',
            boxShadow: vista === 'rag_agente' ? '0 8px 20px -4px rgba(245, 158, 11, 0.45)' : 'none',
          }}
        >
          <IconVectorNodes />
          <span>2 · Buscador Vectorial ChromaDB & Agente Controlado</span>
        </button>
      </nav>

      {/* Asymmetrical Bento Hero + Telemetry Deck */}
      <header className="bento-hero-grid reveal-up">
        <div className="bezel-shell">
          <div className="bezel-core" style={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '1.25rem' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap', marginBottom: '0.85rem' }}>
                <span style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.28rem 0.75rem',
                  borderRadius: '9999px',
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.18em',
                  background: 'rgba(16, 185, 129, 0.14)',
                  color: '#34d399',
                  border: '1px solid rgba(16, 185, 129, 0.28)',
                }}>
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981', boxShadow: '0 0 8px #10b981' }} />
                  Caso N.° 08 · COIP & LOTTTSV
                </span>
                <span className="tabular-nums" style={{ fontSize: '0.76rem', color: '#64748b', fontWeight: 500 }}>
                  UNIANDES · SBU 2026: $482.00 USD
                </span>
              </div>

              <h1 style={{
                fontSize: 'clamp(2rem, 3.4vw, 2.75rem)',
                fontWeight: 800,
                letterSpacing: '-0.04em',
                lineHeight: 1.08,
                color: '#f8fafc',
              }}>
                Vía Segura
              </h1>
              <p style={{
                color: '#94a3b8',
                fontSize: '0.96rem',
                maxWidth: '62ch',
                marginTop: '0.55rem',
                lineHeight: 1.6,
              }}>
                Simulador educativo de situaciones viales con cálculo determinista en Python, índice vectorial ChromaDB (<code className="tabular-nums" style={{ fontSize: '0.84rem', color: '#cbd5e1' }}>intfloat/multilingual-e5-small</code>) y agente con despacho nativo de herramientas.
              </p>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              {[
                '641 Artículos Indexados · 0 Huérfanos',
                'Tool Calling Nativo · Tope 6 Vueltas',
                'Umbral Coseno d ≤ 0.45',
              ].map((tag) => (
                <span
                  key={tag}
                  className="tabular-nums"
                  style={{
                    fontSize: '0.72rem',
                    color: '#94a3b8',
                    background: 'rgba(255, 255, 255, 0.03)',
                    border: '1px solid rgba(255, 255, 255, 0.07)',
                    borderRadius: '8px',
                    padding: '0.28rem 0.6rem',
                  }}
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Right Bento Telemetry Card */}
        <div className="bezel-shell">
          <div className="bezel-core" style={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.16em', color: '#64748b', fontWeight: 700 }}>
                Telemetría de Sesión
              </span>
              <span className="tabular-nums" style={{ fontSize: '0.72rem', color: '#34d399', background: 'rgba(16, 185, 129, 0.1)', padding: '0.18rem 0.55rem', borderRadius: '9999px' }}>
                Activa · LOPDP
              </span>
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: '0.75rem',
            }}>
              <div style={{
                background: 'rgba(5, 7, 11, 0.55)',
                border: '1px solid rgba(255, 255, 255, 0.06)',
                borderRadius: '16px',
                padding: '0.9rem 0.75rem',
              }}>
                <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94a3b8', fontWeight: 600 }}>
                  Aciertos
                </div>
                <div className="tabular-nums" style={{ fontSize: '1.45rem', fontWeight: 800, color: '#10b981', marginTop: '0.25rem' }}>
                  {estadisticas.aciertos}
                  <span style={{ fontSize: '0.88rem', color: '#64748b', fontWeight: 500 }}>/{estadisticas.total}</span>
                </div>
              </div>

              <div style={{
                background: 'rgba(5, 7, 11, 0.55)',
                border: '1px solid rgba(255, 255, 255, 0.06)',
                borderRadius: '16px',
                padding: '0.9rem 0.75rem',
              }}>
                <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94a3b8', fontWeight: 600 }}>
                  Multas SBU
                </div>
                <div className="tabular-nums" style={{ fontSize: '1.35rem', fontWeight: 800, color: '#f59e0b', marginTop: '0.25rem' }}>
                  ${estadisticas.multasAcumuladasUSD.toFixed(2)}
                </div>
              </div>

              <div style={{
                background: 'rgba(5, 7, 11, 0.55)',
                border: '1px solid rgba(255, 255, 255, 0.06)',
                borderRadius: '16px',
                padding: '0.9rem 0.75rem',
              }}>
                <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94a3b8', fontWeight: 600 }}>
                  Puntos COIP
                </div>
                <div className="tabular-nums" style={{ fontSize: '1.45rem', fontWeight: 800, color: '#f43f5e', marginTop: '0.25rem' }}>
                  -{estadisticas.puntosPerdidos.toFixed(1)}
                </div>
              </div>
            </div>

            <div style={{ fontSize: '0.75rem', color: '#64748b', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Cálculo determinista en código</span>
              <span className="tabular-nums">RO 512 (2021)</span>
            </div>
          </div>
        </div>
      </header>

      {vista === 'simulador' && (
        <>
          {/* Scenario Configuration Double-Bezel Bar */}
          <section className="bezel-shell reveal-up" aria-label="Configuración del escenario vial">
            <div className="bezel-core" style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '1.25rem',
              alignItems: 'flex-end',
              justifyContent: 'space-between',
            }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1.15rem', flex: 1 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', minWidth: '210px' }}>
                  <label style={{ fontSize: '0.72rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                    Perfil del Ciudadano
                  </label>
                  <select
                    value={perfil}
                    onChange={(e) => setPerfil(e.target.value as Perfil)}
                    disabled={estado === 'cargando'}
                    className="control-input"
                    style={{ cursor: 'pointer' }}
                  >
                    <option value="conductor_particular">Conductor Particular (Lic. B)</option>
                    <option value="conductor_profesional">Conductor Profesional (Lic. C/D/E)</option>
                    <option value="motociclista">Motociclista (Lic. A)</option>
                    <option value="ciclista">Ciclista</option>
                    <option value="peaton">Peatón</option>
                  </select>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', minWidth: '210px' }}>
                  <label style={{ fontSize: '0.72rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                    Nivel de Dificultad
                  </label>
                  <select
                    value={dificultad}
                    onChange={(e) => setDificultad(e.target.value as Dificultad)}
                    disabled={estado === 'cargando'}
                    className="control-input"
                    style={{ cursor: 'pointer' }}
                  >
                    <option value="baja">Baja (Situación cotidiana)</option>
                    <option value="media">Media (Dilema con agente / señal)</option>
                    <option value="alta">Alta (Condiciones complejas / clima)</option>
                  </select>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', flex: 1, minWidth: '220px' }}>
                  <label style={{ fontSize: '0.72rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                    Tema Vial Opcional
                  </label>
                  <input
                    type="text"
                    placeholder="Ej. semáforo, paso cebra, velocidad..."
                    value={tema}
                    onChange={(e) => setTema(e.target.value)}
                    disabled={estado === 'cargando'}
                    maxLength={100}
                    className="control-input"
                  />
                </div>
              </div>

              <button
                onClick={solicitarEscenario}
                disabled={estado === 'cargando' || estado === 'reintentar'}
                className="btn-island"
                style={{
                  background: estado === 'reintentar'
                    ? '#334155'
                    : 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                  color: estado === 'reintentar' ? '#cbd5e1' : '#03120c',
                  boxShadow: estado === 'reintentar' ? 'none' : '0 10px 26px -6px rgba(16, 185, 129, 0.45)',
                  cursor: estado === 'cargando' || estado === 'reintentar' ? 'not-allowed' : 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                <span>
                  {estado === 'cargando'
                    ? 'Generando escenario...'
                    : estado === 'reintentar'
                    ? `Espera ${cuentaRegresiva}s`
                    : 'Generar Escenario'}
                </span>
                <span className="btn-icon-wrap" style={{ color: '#fff' }}>
                  <IconArrowUpRight />
                </span>
              </button>
            </div>
          </section>

          {estado === 'reintentar' && (
            <div className="bezel-shell reveal-up" style={{ borderColor: 'rgba(245, 158, 11, 0.35)' }}>
              <div className="bezel-core" style={{
                background: 'rgba(245, 158, 11, 0.08)',
                display: 'flex',
                alignItems: 'center',
                gap: '0.9rem',
                color: '#fbbf24',
                padding: '1.1rem 1.4rem',
              }}>
                <span className="tabular-nums" style={{ fontSize: '0.85rem', fontWeight: 700, padding: '0.3rem 0.6rem', borderRadius: '8px', background: 'rgba(245, 158, 11, 0.2)' }}>
                  HTTP 429
                </span>
                <div>
                  <strong style={{ display: 'block', fontSize: '0.95rem' }}>Límite de velocidad activo (RFC 9457)</strong>
                  <span style={{ fontSize: '0.88rem', color: '#fde68a' }}>
                    {mensajeError} <strong className="tabular-nums">{cuentaRegresiva} segundos</strong>.
                  </span>
                </div>
              </div>
            </div>
          )}

          {estado === 'error_servidor' && (
            <div className="bezel-shell reveal-up" style={{ borderColor: 'rgba(244, 63, 94, 0.35)' }}>
              <div className="bezel-core" style={{
                background: 'rgba(244, 63, 94, 0.08)',
                display: 'flex',
                alignItems: 'center',
                gap: '0.9rem',
                color: '#fda4af',
                padding: '1.1rem 1.4rem',
              }}>
                <span className="tabular-nums" style={{ fontSize: '0.8rem', fontWeight: 700, padding: '0.3rem 0.6rem', borderRadius: '8px', background: 'rgba(244, 63, 94, 0.2)' }}>
                  ALERTA
                </span>
                <div>
                  <strong style={{ display: 'block', fontSize: '0.95rem' }}>No se pudo completar la operación</strong>
                  <span style={{ fontSize: '0.88rem' }}>{mensajeError}</span>
                </div>
              </div>
            </div>
          )}

          {/* Skeleton Loading State when generating scenario */}
          {estado === 'cargando' && !escenario && (
            <div className="bezel-shell reveal-up">
              <div className="bezel-core" style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
                <div className="skeleton-bar" style={{ width: '240px', height: '22px' }} />
                <div className="skeleton-bar" style={{ width: '92%', height: '32px' }} />
                <div className="skeleton-bar" style={{ width: '76%', height: '24px' }} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.5rem' }}>
                  {[1, 2, 3, 4].map((n) => (
                    <div key={n} className="skeleton-bar" style={{ width: '100%', height: '58px', borderRadius: '16px' }} />
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Composed Empty State before first scenario */}
          {estado === 'inactiva' && !escenario && (
            <div className="bezel-shell reveal-up">
              <div className="bezel-core" style={{
                padding: '2.5rem 2rem',
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '1.5rem',
              }}>
                <div style={{ maxWidth: '58ch' }}>
                  <span style={{
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.16em',
                    color: '#34d399',
                  }}>
                    Entrenamiento Normativo Interactivo
                  </span>
                  <h2 style={{ fontSize: '1.35rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.35rem', letterSpacing: '-0.02em' }}>
                    Selecciona un perfil vial y genera tu primer dilema jurídico
                  </h2>
                  <p style={{ color: '#94a3b8', fontSize: '0.92rem', marginTop: '0.45rem' }}>
                    Cada escenario vincula una situación realista de tránsito en Ecuador con su tipificación exacta en el COIP y calcula la sanción pecuniaria usando el Salario Básico Unificado 2026 ($482.00 USD) sin alucinaciones aritméticas.
                  </p>
                </div>
                <button
                  onClick={solicitarEscenario}
                  className="btn-island"
                  style={{
                    background: 'rgba(16, 185, 129, 0.14)',
                    color: '#34d399',
                    border: '1px solid rgba(16, 185, 129, 0.35)',
                  }}
                >
                  <span>Iniciar Simulación Ahora</span>
                  <span className="btn-icon-wrap" style={{ color: '#34d399' }}>
                    <IconArrowUpRight />
                  </span>
                </button>
              </div>
            </div>
          )}

          {escenario && (
            <main className="bezel-shell reveal-up">
              <div className="bezel-core" style={{ padding: '2.1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1.35rem' }}>
                  <span style={{
                    fontSize: '0.74rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.14em',
                    color: '#34d399',
                    background: 'rgba(16, 185, 129, 0.12)',
                    border: '1px solid rgba(16, 185, 129, 0.25)',
                    padding: '0.3rem 0.75rem',
                    borderRadius: '9999px',
                  }}>
                    Escenario · {escenario.perfil.replace('_', ' ')} · Dificultad {escenario.nivel_dificultad}
                  </span>
                  <span className="tabular-nums" style={{ fontSize: '0.78rem', color: '#64748b' }}>
                    ID: {escenario.id_escenario}
                  </span>
                </div>

                <h2 style={{
                  fontSize: 'clamp(1.15rem, 2vw, 1.38rem)',
                  fontWeight: 600,
                  color: '#f8fafc',
                  lineHeight: 1.55,
                  letterSpacing: '-0.015em',
                  marginBottom: '1.85rem',
                }}>
                  {escenario.situacion}
                </h2>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', marginBottom: '1.85rem' }}>
                  {escenario.opciones.map((opc) => {
                    const estaSeleccionada = opcionSeleccionada === opc.id_opcion;
                    let borde = estaSeleccionada ? '#10b981' : 'rgba(255, 255, 255, 0.08)';
                    let fondo = estaSeleccionada ? 'rgba(16, 185, 129, 0.11)' : 'rgba(7, 11, 18, 0.65)';

                    if (resultado) {
                      if (opc.id_opcion === resultado.respuesta_correcta) {
                        borde = '#10b981';
                        fondo = 'rgba(16, 185, 129, 0.16)';
                      } else if (estaSeleccionada && !resultado.es_correcta) {
                        borde = '#f43f5e';
                        fondo = 'rgba(244, 63, 94, 0.16)';
                      }
                    }

                    return (
                      <button
                        key={opc.id_opcion}
                        onClick={() => !resultado && setOpcionSeleccionada(opc.id_opcion)}
                        disabled={!!resultado || estado === 'cargando'}
                        className="option-card"
                        style={{
                          background: fondo,
                          border: `1.5px solid ${borde}`,
                          cursor: resultado ? 'default' : 'pointer',
                        }}
                      >
                        <span
                          className="tabular-nums"
                          style={{
                            width: '34px',
                            height: '34px',
                            borderRadius: '10px',
                            background: estaSeleccionada ? '#10b981' : 'rgba(255, 255, 255, 0.06)',
                            color: estaSeleccionada ? '#04130d' : '#e2e8f0',
                            border: '1px solid rgba(255, 255, 255, 0.1)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontWeight: 700,
                            fontSize: '0.88rem',
                            flexShrink: 0,
                          }}
                        >
                          {opc.id_opcion}
                        </span>
                        <span style={{ marginTop: '0.18rem', lineHeight: 1.55 }}>
                          {opc.texto}
                        </span>
                      </button>
                    );
                  })}
                </div>

                {!resultado && (
                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <button
                      onClick={enviarRespuesta}
                      disabled={!opcionSeleccionada || estado === 'cargando'}
                      className="btn-island"
                      style={{
                        background: !opcionSeleccionada
                          ? 'rgba(255, 255, 255, 0.06)'
                          : 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                        color: !opcionSeleccionada ? '#64748b' : '#03120c',
                        cursor: !opcionSeleccionada ? 'not-allowed' : 'pointer',
                      }}
                    >
                      <span>{estado === 'cargando' ? 'Evaluando...' : 'Confirmar Decisión'}</span>
                      <span className="btn-icon-wrap" style={{ color: !opcionSeleccionada ? '#64748b' : '#fff' }}>
                        <IconArrowUpRight />
                      </span>
                    </button>
                  </div>
                )}

                {resultado && (
                  <div
                    className="reveal-up"
                    style={{
                      marginTop: '2rem',
                      borderTop: '1px solid rgba(255, 255, 255, 0.08)',
                      paddingTop: '1.85rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '1.25rem',
                    }}
                  >
                    <div style={{
                      background: resultado.es_correcta ? 'rgba(16, 185, 129, 0.09)' : 'rgba(244, 63, 94, 0.09)',
                      border: `1.5px solid ${resultado.es_correcta ? 'rgba(16, 185, 129, 0.45)' : 'rgba(244, 63, 94, 0.45)'}`,
                      borderRadius: '20px',
                      padding: '1.6rem',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
                        <span
                          className="tabular-nums"
                          style={{
                            padding: '0.25rem 0.65rem',
                            borderRadius: '9999px',
                            fontSize: '0.72rem',
                            fontWeight: 700,
                            letterSpacing: '0.1em',
                            textTransform: 'uppercase',
                            background: resultado.es_correcta ? 'rgba(16, 185, 129, 0.2)' : 'rgba(244, 63, 94, 0.2)',
                            color: resultado.es_correcta ? '#34d399' : '#fb7185',
                          }}
                        >
                          {resultado.es_correcta ? 'Veredicto: Conforme' : 'Veredicto: Infracción'}
                        </span>
                        <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: resultado.es_correcta ? '#34d399' : '#fb7185', letterSpacing: '-0.02em' }}>
                          {resultado.es_correcta ? 'Decisión Correcta Conforme a la Ley' : 'Infracción Detectada: Conducta no permitida'}
                        </h3>
                      </div>

                      <p style={{ color: '#e2e8f0', fontSize: '0.98rem', lineHeight: 1.65, marginBottom: '1.35rem' }}>
                        {resultado.explicacion_educativa}
                      </p>

                      <div style={{
                        background: 'rgba(5, 7, 11, 0.65)',
                        border: '1px solid rgba(255, 255, 255, 0.07)',
                        borderRadius: '16px',
                        padding: '1.25rem',
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
                        gap: '1.1rem',
                      }}>
                        <div>
                          <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94a3b8', fontWeight: 600 }}>
                            Artículo y Norma
                          </span>
                          <div className="tabular-nums" style={{ fontWeight: 700, color: '#f8fafc', fontSize: '0.96rem', marginTop: '0.2rem' }}>
                            {resultado.contravencion.articulo} · {resultado.contravencion.clase}
                          </div>
                          <div style={{ fontSize: '0.78rem', color: '#64748b' }}>{resultado.contravencion.norma}</div>
                        </div>

                        <div>
                          <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94a3b8', fontWeight: 600 }}>
                            Multa Pecuniaria (SBU: ${resultado.sancion.sbu_usd.toFixed(2)})
                          </span>
                          <div className="tabular-nums" style={{ fontWeight: 800, color: '#f59e0b', fontSize: '1.2rem', marginTop: '0.2rem' }}>
                            ${resultado.sancion.multa_usd.toFixed(2)} USD
                          </div>
                          <div className="tabular-nums" style={{ fontSize: '0.78rem', color: '#64748b' }}>
                            ({resultado.sancion.porcentaje_sbu}% del Salario Básico)
                          </div>
                        </div>

                        <div>
                          <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94a3b8', fontWeight: 600 }}>
                            Puntos COIP / Vigentes (RO 512)
                          </span>
                          <div className="tabular-nums" style={{ fontWeight: 800, color: '#f43f5e', fontSize: '1.2rem', marginTop: '0.2rem' }}>
                            -{resultado.sancion.puntos_reducidos} pts{' '}
                            <span style={{ fontSize: '0.82rem', color: '#94a3b8', fontWeight: 500 }}>
                              (Hoy: -{resultado.sancion.puntos_aplicables ?? resultado.sancion.puntos_reducidos} pts)
                            </span>
                          </div>
                          <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
                            {resultado.sancion.pena_adicional
                              ? resultado.sancion.pena_adicional
                              : resultado.sancion.dias_privacion_libertad > 0
                              ? `+ ${resultado.sancion.dias_privacion_libertad} días privación libertad`
                              : 'Reforma 2021: sin resta de puntos en 3ª–7ª clase'}
                          </div>
                        </div>
                      </div>

                      {resultado.contravencion.texto_literal_coip && (
                        <div style={{
                          marginTop: '1.1rem',
                          padding: '0.95rem 1.15rem',
                          borderRadius: '12px',
                          background: 'rgba(10, 14, 23, 0.85)',
                          borderLeft: '3px solid #10b981',
                          fontSize: '0.88rem',
                          color: '#cbd5e1',
                        }}>
                          <strong style={{ color: '#34d399', display: 'block', marginBottom: '0.25rem' }}>
                            Cita literal verificada ({resultado.contravencion.articulo} · {resultado.contravencion.norma}):
                          </strong>
                          «{resultado.contravencion.texto_literal_coip}»
                        </div>
                      )}
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                      <span style={{ fontSize: '0.8rem', color: '#64748b' }}>{resultado.aviso}</span>
                      <button
                        onClick={solicitarEscenario}
                        className="btn-island"
                        style={{
                          background: 'rgba(255, 255, 255, 0.06)',
                          color: '#f8fafc',
                          border: '1px solid rgba(255, 255, 255, 0.12)',
                        }}
                      >
                        <span>Siguiente Escenario</span>
                        <span className="btn-icon-wrap">
                          <IconArrowUpRight />
                        </span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </main>
          )}
        </>
      )}

      {vista === 'rag_agente' && (
        <section className="bezel-shell reveal-up" aria-label="Consultor RAG y Agente Controlado">
          <div className="bezel-core" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div>
              <span style={{
                display: 'inline-block',
                fontSize: '0.7rem',
                fontWeight: 700,
                color: '#fbbf24',
                textTransform: 'uppercase',
                letterSpacing: '0.16em',
                background: 'rgba(245, 158, 11, 0.12)',
                border: '1px solid rgba(245, 158, 11, 0.28)',
                padding: '0.25rem 0.7rem',
                borderRadius: '9999px',
              }}>
                Módulo 3 · RAG ChromaDB (`intfloat/multilingual-e5-small`) · Agente con Tool Calling
              </span>
              <h2 style={{ fontSize: 'clamp(1.3rem, 2.2vw, 1.6rem)', fontWeight: 800, color: '#f8fafc', marginTop: '0.55rem', letterSpacing: '-0.025em' }}>
                Consultor Normativo con Cita Verificada, Distancia Coseno y Regla de Silencio
              </h2>
              <p style={{ color: '#94a3b8', fontSize: '0.92rem', marginTop: '0.3rem', maxWidth: '72ch' }}>
                El RAG recupera los 5 artículos vigentes más cercanos (<code className="tabular-nums">where={'{"vigente": True}'}</code>), el agente invoca herramientas tipadas con Pydantic para calcular la multa SBU 2026 ($482.00) y verifica la cita dentro de un tope máximo de 6 vueltas.
              </p>
            </div>

            <div style={{ display: 'flex', gap: '0.55rem', flexWrap: 'wrap' }}>
              {EJEMPLOS_SEMANA3.map((ej, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setPreguntaChat(ej.pregunta);
                    setDemoEnvenenado(ej.envenenado);
                    enviarConsultaRAG(ej.pregunta, ej.envenenado);
                  }}
                  style={{
                    background: preguntaChat === ej.pregunta ? 'rgba(245, 158, 11, 0.16)' : 'rgba(255, 255, 255, 0.03)',
                    border: `1px solid ${preguntaChat === ej.pregunta ? 'rgba(245, 158, 11, 0.45)' : 'rgba(255, 255, 255, 0.09)'}`,
                    color: preguntaChat === ej.pregunta ? '#fde68a' : '#cbd5e1',
                    borderRadius: '9999px',
                    padding: '0.45rem 0.9rem',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.35s cubic-bezier(0.32, 0.72, 0, 1)',
                  }}
                >
                  {ej.etiqueta}
                </button>
              ))}
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <input
                type="text"
                value={preguntaChat}
                onChange={(e) => setPreguntaChat(e.target.value)}
                placeholder="Escribe una pregunta en lenguaje ciudadano (ej. Me pasé un semáforo en rojo, ¿cuánto pago?)"
                className="control-input"
                style={{ flex: 1, minWidth: '260px' }}
              />
              <button
                onClick={() => enviarConsultaRAG()}
                disabled={cargandoChat}
                className="btn-island"
                style={{
                  background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
                  color: '#1c1002',
                  boxShadow: '0 10px 26px -6px rgba(245, 158, 11, 0.4)',
                  cursor: cargandoChat ? 'not-allowed' : 'pointer',
                }}
              >
                <span>{cargandoChat ? 'Buscando en ChromaDB...' : 'Consultar RAG + Agente'}</span>
                <span className="btn-icon-wrap" style={{ color: '#fff' }}>
                  <IconArrowUpRight />
                </span>
              </button>
            </div>

            {cargandoChat && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                <div className="skeleton-bar" style={{ width: '100%', height: '48px', borderRadius: '14px' }} />
                <div className="skeleton-bar" style={{ width: '100%', height: '140px', borderRadius: '18px' }} />
              </div>
            )}

            {respuestaChat && !cargandoChat && (
              <div className="reveal-up" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                <div
                  className="tabular-nums"
                  style={{
                    background: 'rgba(245, 158, 11, 0.1)',
                    border: '1px solid rgba(245, 158, 11, 0.35)',
                    borderRadius: '14px',
                    padding: '0.9rem 1.2rem',
                    color: '#fde68a',
                    fontSize: '0.86rem',
                    fontWeight: 600,
                  }}
                >
                  {respuestaChat.resumen_clase}
                </div>

                {respuestaChat.alerta_seguridad && (
                  <div style={{
                    background: 'rgba(244, 63, 94, 0.12)',
                    border: '1.5px solid #f43f5e',
                    borderRadius: '14px',
                    padding: '1rem 1.2rem',
                    color: '#fecdd3',
                    fontSize: '0.9rem',
                  }}>
                    <strong>Defensa Activa contra Inyección Indirecta (Revisión 3):</strong> {respuestaChat.alerta_seguridad}
                  </div>
                )}

                <div style={{
                  background: respuestaChat.abstencion ? 'rgba(244, 63, 94, 0.07)' : 'rgba(16, 185, 129, 0.08)',
                  border: `1.5px solid ${respuestaChat.abstencion ? 'rgba(244, 63, 94, 0.45)' : 'rgba(16, 185, 129, 0.45)'}`,
                  borderRadius: '18px',
                  padding: '1.45rem',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.65rem' }}>
                    <strong style={{ color: respuestaChat.abstencion ? '#fb7185' : '#34d399', fontSize: '1.05rem' }}>
                      {respuestaChat.abstencion
                        ? `Modo Silencio / Derivación (${respuestaChat.tipo})`
                        : `Respuesta Fundamentada · Cita Verificada: ${respuestaChat.citas.join(', ')}`}
                    </strong>
                    <span className="tabular-nums" style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                      Mejor distancia coseno: {respuestaChat.mejor_distancia.toFixed(2)} (umbral: {respuestaChat.umbral_distancia ?? 0.45})
                    </span>
                  </div>
                  <p style={{ color: '#f1f5f9', lineHeight: 1.65, margin: 0 }}>{respuestaChat.respuesta}</p>

                  {respuestaChat.sancion_calculada && (
                    <div style={{
                      marginTop: '1.1rem',
                      background: 'rgba(5, 7, 11, 0.6)',
                      border: '1px solid rgba(255, 255, 255, 0.07)',
                      borderRadius: '14px',
                      padding: '1.05rem',
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
                      gap: '0.85rem',
                    }}>
                      <div>
                        <span style={{ fontSize: '0.7rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                          Cálculo Determinista (`calcular_sancion`)
                        </span>
                        <div className="tabular-nums" style={{ fontWeight: 800, color: '#f59e0b', fontSize: '1.15rem', marginTop: '0.15rem' }}>
                          ${respuestaChat.sancion_calculada.multa_usd.toFixed(2)} USD ({respuestaChat.sancion_calculada.porcentaje_sbu}% SBU)
                        </div>
                      </div>
                      <div>
                        <span style={{ fontSize: '0.7rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                          Puntos Texto COIP / Hoy
                        </span>
                        <div className="tabular-nums" style={{ fontWeight: 800, color: '#f43f5e', fontSize: '1.08rem', marginTop: '0.15rem' }}>
                          -{respuestaChat.sancion_calculada.puntos_texto_coip} pts (Hoy: -{respuestaChat.sancion_calculada.puntos_aplicables_hoy} pts)
                        </div>
                      </div>
                      <div>
                        <span style={{ fontSize: '0.7rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                          Código Tabla Oficial
                        </span>
                        <div className="tabular-nums" style={{ fontWeight: 700, color: '#f8fafc', fontSize: '0.92rem', marginTop: '0.15rem' }}>
                          {respuestaChat.sancion_calculada.codigo_csv} · {respuestaChat.sancion_calculada.id_contravencion}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {respuestaChat.fragmentos.length > 0 && (
                  <div style={{
                    background: 'rgba(5, 7, 11, 0.55)',
                    border: '1px solid rgba(255, 255, 255, 0.07)',
                    borderRadius: '18px',
                    padding: '1.25rem',
                  }}>
                    <h3 style={{ fontSize: '0.92rem', fontWeight: 700, color: '#fbbf24', marginBottom: '0.85rem' }}>
                      Top-5 Vecinos Más Cercanos en ChromaDB (<code className="tabular-nums">where={'{"vigente": True}'}</code> · Modelo <code className="tabular-nums">{respuestaChat.modelo_embeddings || 'intfloat/multilingual-e5-small'}</code>)
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                      {respuestaChat.fragmentos.map((f) => (
                        <div
                          key={f.id}
                          style={{
                            background: f.puesto === 1 ? 'rgba(245, 158, 11, 0.09)' : 'rgba(15, 23, 42, 0.6)',
                            border: `1px solid ${f.puesto === 1 ? 'rgba(245, 158, 11, 0.38)' : 'rgba(255, 255, 255, 0.06)'}`,
                            borderRadius: '12px',
                            padding: '0.8rem 1rem',
                            fontSize: '0.86rem',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', fontWeight: 700, color: '#f8fafc', marginBottom: '0.28rem' }}>
                            <span>#{f.puesto} · {f.documento} — Art. {f.articulo} ({f.id})</span>
                            <span className="tabular-nums" style={{ color: '#fbbf24', fontSize: '0.78rem' }}>
                              distancia coseno: {f.distancia.toFixed(2)} | vigente: {String(f.metadatos.vigente)}
                            </span>
                          </div>
                          <div style={{ color: '#94a3b8', fontSize: '0.82rem' }}>
                            {f.texto.slice(0, 220)}{f.texto.length > 220 ? '…' : ''}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(310px, 1fr))',
                  gap: '1rem',
                }}>
                  <div style={{
                    background: 'rgba(5, 7, 11, 0.55)',
                    border: '1px solid rgba(255, 255, 255, 0.07)',
                    borderRadius: '18px',
                    padding: '1.2rem',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.7rem' }}>
                      <strong style={{ color: '#34d399', fontSize: '0.9rem' }}>Agente con Tool Calling Nativo</strong>
                      <span className="tabular-nums" style={{ fontSize: '0.8rem', color: '#fbbf24' }}>
                        Vueltas: {respuestaChat.agente.vueltas_usadas} / {respuestaChat.agente.tope_vueltas}
                      </span>
                    </div>
                    {respuestaChat.agente.bitacora.map((b, idx) => (
                      <div key={idx} style={{ fontSize: '0.8rem', color: '#cbd5e1', marginBottom: '0.5rem', borderLeft: '2px solid #10b981', paddingLeft: '0.65rem' }}>
                        <strong className="tabular-nums" style={{ color: '#f8fafc' }}>Vuelta {b.vuelta} ({b.herramienta}):</strong> {b.detalle}
                      </div>
                    ))}
                  </div>

                  <div style={{
                    background: 'rgba(5, 7, 11, 0.55)',
                    border: '1px solid rgba(255, 255, 255, 0.07)',
                    borderRadius: '18px',
                    padding: '1.2rem',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.7rem' }}>
                      <strong style={{ color: '#a78bfa', fontSize: '0.9rem' }}>Automatización Inteligente (4 Estaciones)</strong>
                      <span className="tabular-nums" style={{ fontSize: '0.8rem', color: '#c4b5fd' }}>
                        Confianza: {(respuestaChat.automatizacion.confianza * 100).toFixed(0)}%
                      </span>
                    </div>
                    {respuestaChat.automatizacion.estaciones.map((st, idx) => (
                      <div key={idx} style={{ fontSize: '0.8rem', color: '#cbd5e1', marginBottom: '0.5rem', borderLeft: '2px solid #8b5cf6', paddingLeft: '0.65rem' }}>
                        <strong style={{ color: '#f8fafc' }}>{st.estacion} [{st.actor}]:</strong> {st.resultado}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      <footer style={{
        marginTop: 'auto',
        borderTop: '1px solid rgba(255, 255, 255, 0.06)',
        paddingTop: '1.5rem',
        fontSize: '0.82rem',
        color: '#64748b',
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        gap: '1rem',
      }}>
        <span>Simulador Vial «Vía Segura» · Escuela de Conducción UNIANDES · Caso N.° 08</span>
        <span>Protección de Datos: Sesión anónima conforme a la LOPDP (Ecuador) · Cero recolección de PII</span>
      </footer>
    </div>
  );
}

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
    <div style={{ maxWidth: '1040px', margin: '0 auto', padding: '2rem 1.5rem', minHeight: '100vh', display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <header style={{
        background: 'linear-gradient(180deg, rgba(31, 41, 55, 0.6) 0%, rgba(17, 24, 39, 0.8) 100%)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '24px',
        padding: '2rem',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), inset 0 1px 1px rgba(255, 255, 255, 0.1)',
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: '1.5rem'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '0.2rem 0.65rem',
              borderRadius: '9999px',
              fontSize: '0.75rem',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.12em',
              background: 'rgba(16, 185, 129, 0.15)',
              color: '#34d399',
              border: '1px solid rgba(16, 185, 129, 0.3)'
            }}>
              Caso N.° 08 · COIP, LOTTTSV & RAG
            </span>
            <span style={{ fontSize: '0.8rem', color: '#6b7280' }}>Seminario Titulación UNIANDES · SBU 2026: $482.00</span>
          </div>
          <h1 style={{ fontSize: '2.1rem', fontWeight: 800, letterSpacing: '-0.03em', color: '#ffffff' }}>
            Vía Segura
          </h1>
          <p style={{ color: '#9ca3af', fontSize: '0.95rem', maxWidth: '580px', marginTop: '0.25rem' }}>
            Simulador educativo de dilemas viales, base vectorial ChromaDB (`multilingual-e5-small`) y agente de alcance controlado.
          </p>
        </div>

        <div style={{
          background: 'rgba(0, 0, 0, 0.35)',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          borderRadius: '16px',
          padding: '1rem 1.25rem',
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '1.25rem',
          textAlign: 'center'
        }}>
          <div>
            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#9ca3af', fontWeight: 600 }}>Aciertos</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#10b981' }}>
              {estadisticas.aciertos} <span style={{ fontSize: '0.9rem', color: '#6b7280' }}>/ {estadisticas.total}</span>
            </div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#9ca3af', fontWeight: 600 }}>Multas SBU</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#f59e0b' }}>
              ${estadisticas.multasAcumuladasUSD.toFixed(2)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#9ca3af', fontWeight: 600 }}>Puntos COIP</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#f43f5e' }}>
              -{estadisticas.puntosPerdidos.toFixed(1)}
            </div>
          </div>
        </div>
      </header>

      <nav style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        <button
          onClick={() => setVista('simulador')}
          style={{
            background: vista === 'simulador' ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' : 'rgba(17, 24, 39, 0.7)',
            color: '#fff',
            border: vista === 'simulador' ? 'none' : '1px solid rgba(255, 255, 255, 0.12)',
            borderRadius: '12px',
            padding: '0.7rem 1.35rem',
            fontWeight: 700,
            fontSize: '0.92rem',
            cursor: 'pointer'
          }}
        >
          1 · Simulador de Dilemas Viales (Escenarios IA + Código)
        </button>
        <button
          onClick={() => setVista('rag_agente')}
          style={{
            background: vista === 'rag_agente' ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)' : 'rgba(17, 24, 39, 0.7)',
            color: '#fff',
            border: vista === 'rag_agente' ? 'none' : '1px solid rgba(255, 255, 255, 0.12)',
            borderRadius: '12px',
            padding: '0.7rem 1.35rem',
            fontWeight: 700,
            fontSize: '0.92rem',
            cursor: 'pointer'
          }}
        >
          2 · Buscador Vectorial ChromaDB & Agente Controlado (Semana 3)
        </button>
      </nav>

      {vista === 'simulador' && (
        <>
          <section style={{
            background: 'rgba(17, 24, 39, 0.7)',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            borderRadius: '20px',
            padding: '1.5rem',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '1.25rem',
            alignItems: 'flex-end',
            justifyContent: 'space-between'
          }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1.25rem', flex: 1 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Perfil del Ciudadano
                </label>
                <select
                  value={perfil}
                  onChange={(e) => setPerfil(e.target.value as Perfil)}
                  disabled={estado === 'cargando'}
                  style={{
                    background: '#1f2937',
                    color: '#fff',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    borderRadius: '10px',
                    padding: '0.6rem 0.9rem',
                    fontSize: '0.92rem',
                    outline: 'none',
                    cursor: 'pointer'
                  }}
                >
                  <option value="conductor_particular">Conductor Particular (Lic. B)</option>
                  <option value="conductor_profesional">Conductor Profesional (Lic. C/D/E)</option>
                  <option value="motociclista">Motociclista (Lic. A)</option>
                  <option value="ciclista">Ciclista</option>
                  <option value="peaton">Peatón</option>
                </select>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Nivel de Dificultad
                </label>
                <select
                  value={dificultad}
                  onChange={(e) => setDificultad(e.target.value as Dificultad)}
                  disabled={estado === 'cargando'}
                  style={{
                    background: '#1f2937',
                    color: '#fff',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    borderRadius: '10px',
                    padding: '0.6rem 0.9rem',
                    fontSize: '0.92rem',
                    outline: 'none',
                    cursor: 'pointer'
                  }}
                >
                  <option value="baja">Baja (Situación cotidiana)</option>
                  <option value="media">Media (Dilema con agente / señal)</option>
                  <option value="alta">Alta (Condiciones complejas / clima)</option>
                </select>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', flex: 1, minWidth: '200px' }}>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Tema Vial Opcional
                </label>
                <input
                  type="text"
                  placeholder="Ej. semáforo, paso cebra, velocidad..."
                  value={tema}
                  onChange={(e) => setTema(e.target.value)}
                  disabled={estado === 'cargando'}
                  maxLength={100}
                  style={{
                    background: '#1f2937',
                    color: '#fff',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    borderRadius: '10px',
                    padding: '0.6rem 0.9rem',
                    fontSize: '0.92rem',
                    outline: 'none'
                  }}
                />
              </div>
            </div>

            <button
              onClick={solicitarEscenario}
              disabled={estado === 'cargando' || estado === 'reintentar'}
              style={{
                background: estado === 'reintentar' ? '#4b5563' : 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                color: '#fff',
                border: 'none',
                borderRadius: '12px',
                padding: '0.75rem 1.75rem',
                fontSize: '0.95rem',
                fontWeight: 700,
                cursor: estado === 'cargando' || estado === 'reintentar' ? 'not-allowed' : 'pointer',
                boxShadow: '0 4px 14px rgba(16, 185, 129, 0.3)',
                transition: 'all 0.2s ease',
                whiteSpace: 'nowrap'
              }}
            >
              {estado === 'cargando' ? 'Generando escenario...' : estado === 'reintentar' ? `Espera ${cuentaRegresiva}s` : 'Generar Escenario'}
            </button>
          </section>

          {estado === 'reintentar' && (
            <div style={{
              background: 'rgba(245, 158, 11, 0.1)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              borderRadius: '14px',
              padding: '1rem 1.25rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              color: '#fbbf24'
            }}>
              <span style={{ fontSize: '1.4rem' }}>⏳</span>
              <div>
                <strong style={{ display: 'block' }}>Límite de solicitudes alcanzado (RFC 9457 · 429)</strong>
                <span>{mensajeError} <strong>{cuentaRegresiva} segundos</strong>.</span>
              </div>
            </div>
          )}

          {estado === 'error_servidor' && (
            <div style={{
              background: 'rgba(244, 63, 94, 0.1)',
              border: '1px solid rgba(244, 63, 94, 0.3)',
              borderRadius: '14px',
              padding: '1rem 1.25rem',
              color: '#fda4af',
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem'
            }}>
              <span style={{ fontSize: '1.4rem' }}>⚠️</span>
              <div>
                <strong style={{ display: 'block' }}>Atención</strong>
                <span>{mensajeError}</span>
              </div>
            </div>
          )}

          {escenario && (
            <main style={{
              background: '#111827',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '24px',
              padding: '2rem',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                <span style={{
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.1em',
                  color: '#34d399',
                  background: 'rgba(16, 185, 129, 0.1)',
                  padding: '0.25rem 0.6rem',
                  borderRadius: '6px'
                }}>
                  Escenario: {escenario.perfil.replace('_', ' ')} · Dificultad {escenario.nivel_dificultad}
                </span>
                <span style={{ fontSize: '0.8rem', color: '#6b7280' }}>ID: {escenario.id_escenario}</span>
              </div>

              <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: '#f3f4f6', lineHeight: 1.6, marginBottom: '2rem' }}>
                {escenario.situacion}
              </h2>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '2rem' }}>
                {escenario.opciones.map((opc) => {
                  const estaSeleccionada = opcionSeleccionada === opc.id_opcion;
                  let borde = estaSeleccionada ? '#10b981' : 'rgba(255, 255, 255, 0.08)';
                  let fondo = estaSeleccionada ? 'rgba(16, 185, 129, 0.1)' : 'rgba(31, 41, 55, 0.5)';

                  if (resultado) {
                    if (opc.id_opcion === resultado.respuesta_correcta) {
                      borde = '#10b981';
                      fondo = 'rgba(16, 185, 129, 0.15)';
                    } else if (estaSeleccionada && !resultado.es_correcta) {
                      borde = '#f43f5e';
                      fondo = 'rgba(244, 63, 94, 0.15)';
                    }
                  }

                  return (
                    <button
                      key={opc.id_opcion}
                      onClick={() => !resultado && setOpcionSeleccionada(opc.id_opcion)}
                      disabled={!!resultado || estado === 'cargando'}
                      style={{
                        background: fondo,
                        border: `1.5px solid ${borde}`,
                        borderRadius: '16px',
                        padding: '1.1rem 1.25rem',
                        textAlign: 'left',
                        color: '#f9fafb',
                        fontSize: '1rem',
                        cursor: resultado ? 'default' : 'pointer',
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '1rem',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      <span style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '50%',
                        background: estaSeleccionada ? '#10b981' : '#374151',
                        color: '#fff',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 700,
                        fontSize: '0.9rem',
                        flexShrink: 0
                      }}>
                        {opc.id_opcion}
                      </span>
                      <span style={{ marginTop: '0.2rem', lineHeight: 1.5 }}>
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
                    style={{
                      background: !opcionSeleccionada ? '#374151' : 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                      color: '#fff',
                      border: 'none',
                      borderRadius: '12px',
                      padding: '0.8rem 2rem',
                      fontSize: '1rem',
                      fontWeight: 700,
                      cursor: !opcionSeleccionada ? 'not-allowed' : 'pointer'
                    }}
                  >
                    {estado === 'cargando' ? 'Evaluando...' : 'Confirmar Decisión'}
                  </button>
                </div>
              )}

              {resultado && (
                <div style={{
                  marginTop: '2rem',
                  borderTop: '1px solid rgba(255, 255, 255, 0.1)',
                  paddingTop: '2rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '1.25rem'
                }}>
                  <div style={{
                    background: resultado.es_correcta ? 'rgba(16, 185, 129, 0.12)' : 'rgba(244, 63, 94, 0.12)',
                    border: `1.5px solid ${resultado.es_correcta ? '#10b981' : '#f43f5e'}`,
                    borderRadius: '16px',
                    padding: '1.5rem'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
                      <span style={{ fontSize: '1.6rem' }}>{resultado.es_correcta ? '✅' : '❌'}</span>
                      <h3 style={{ fontSize: '1.3rem', fontWeight: 800, color: resultado.es_correcta ? '#34d399' : '#fb7185' }}>
                        {resultado.es_correcta ? '¡Decisión Correcta Conforme a la Ley!' : 'Infracción Detectada: Conducta no permitida'}
                      </h3>
                    </div>

                    <p style={{ color: '#e5e7eb', fontSize: '1rem', lineHeight: 1.6, marginBottom: '1.25rem' }}>
                      {resultado.explicacion_educativa}
                    </p>

                    <div style={{
                      background: 'rgba(0, 0, 0, 0.3)',
                      border: '1px solid rgba(255, 255, 255, 0.06)',
                      borderRadius: '12px',
                      padding: '1.25rem',
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                      gap: '1rem'
                    }}>
                      <div>
                        <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#9ca3af', fontWeight: 600 }}>Artículo y Norma</span>
                        <div style={{ fontWeight: 700, color: '#fff', fontSize: '0.95rem' }}>
                          {resultado.contravencion.articulo} · {resultado.contravencion.clase}
                        </div>
                        <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>{resultado.contravencion.norma}</div>
                      </div>

                      <div>
                        <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#9ca3af', fontWeight: 600 }}>Multa Pecuniaria (SBU: ${resultado.sancion.sbu_usd.toFixed(2)})</span>
                        <div style={{ fontWeight: 800, color: '#f59e0b', fontSize: '1.15rem' }}>
                          ${resultado.sancion.multa_usd.toFixed(2)} USD
                        </div>
                        <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>({resultado.sancion.porcentaje_sbu}% del Salario Básico)</div>
                      </div>

                      <div>
                        <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#9ca3af', fontWeight: 600 }}>Puntos COIP / Vigentes (RO 512)</span>
                        <div style={{ fontWeight: 800, color: '#f43f5e', fontSize: '1.15rem' }}>
                          -{resultado.sancion.puntos_reducidos} pts <span style={{ fontSize: '0.85rem', color: '#9ca3af', fontWeight: 600 }}>(Hoy: -{resultado.sancion.puntos_aplicables ?? resultado.sancion.puntos_reducidos} pts)</span>
                        </div>
                        <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>
                          {resultado.sancion.pena_adicional ? resultado.sancion.pena_adicional : resultado.sancion.dias_privacion_libertad > 0 ? `+ ${resultado.sancion.dias_privacion_libertad} días privación libertad` : 'Reforma 2021: sin resta de puntos en 3ª–7ª clase'}
                        </div>
                      </div>
                    </div>
                    {resultado.contravencion.texto_literal_coip && (
                      <div style={{
                        marginTop: '1rem',
                        padding: '0.85rem 1rem',
                        borderRadius: '10px',
                        background: 'rgba(17, 24, 39, 0.75)',
                        borderLeft: '3px solid #10b981',
                        fontSize: '0.88rem',
                        color: '#d1d5db'
                      }}>
                        <strong style={{ color: '#34d399', display: 'block', marginBottom: '0.2rem' }}>
                          Cita literal verificada ({resultado.contravencion.articulo} · {resultado.contravencion.norma}):
                        </strong>
                        «{resultado.contravencion.texto_literal_coip}»
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.8rem', color: '#6b7280' }}>{resultado.aviso}</span>
                    <button
                      onClick={solicitarEscenario}
                      style={{
                        background: '#1f2937',
                        border: '1px solid rgba(255, 255, 255, 0.15)',
                        color: '#fff',
                        borderRadius: '10px',
                        padding: '0.65rem 1.4rem',
                        fontWeight: 700,
                        cursor: 'pointer'
                      }}
                    >
                      Siguiente Escenario ➔
                    </button>
                  </div>
                </div>
              )}
            </main>
          )}
        </>
      )}

      {vista === 'rag_agente' && (
        <section style={{
          background: '#111827',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '24px',
          padding: '2rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.5rem'
        }}>
          <div>
            <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#f59e0b', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              Módulo 3 · RAG · ChromaDB (`intfloat/multilingual-e5-small`) · Agente de Alcance Controlado
            </span>
            <h2 style={{ fontSize: '1.45rem', fontWeight: 800, color: '#fff', marginTop: '0.25rem' }}>
              Consultor Normativo con Cita Verificada, Distancia Coseno y Regla de Silencio
            </h2>
            <p style={{ color: '#9ca3af', fontSize: '0.92rem', marginTop: '0.25rem' }}>
              El RAG recupera los 5 artículos vigentes más cercanos (`where={'{"vigente": True}'}`), el código calcula la multa con el SBU 2026 ($482.00) y el agente verifica la cita dentro de un tope máximo de 6 vueltas.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
            {EJEMPLOS_SEMANA3.map((ej, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setPreguntaChat(ej.pregunta);
                  setDemoEnvenenado(ej.envenenado);
                  enviarConsultaRAG(ej.pregunta, ej.envenenado);
                }}
                style={{
                  background: 'rgba(31, 41, 55, 0.85)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#e5e7eb',
                  borderRadius: '10px',
                  padding: '0.5rem 0.85rem',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  cursor: 'pointer'
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
              style={{
                flex: 1,
                minWidth: '260px',
                background: '#1f2937',
                color: '#fff',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: '12px',
                padding: '0.75rem 1rem',
                fontSize: '0.95rem'
              }}
            />
            <button
              onClick={() => enviarConsultaRAG()}
              disabled={cargandoChat}
              style={{
                background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
                color: '#111827',
                border: 'none',
                borderRadius: '12px',
                padding: '0.75rem 1.5rem',
                fontWeight: 800,
                cursor: cargandoChat ? 'not-allowed' : 'pointer'
              }}
            >
              {cargandoChat ? 'Buscando en ChromaDB...' : 'Consultar RAG + Agente'}
            </button>
          </div>

          {respuestaChat && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div style={{
                background: 'rgba(245, 158, 11, 0.12)',
                border: '1.5px solid rgba(245, 158, 11, 0.4)',
                borderRadius: '14px',
                padding: '0.9rem 1.2rem',
                color: '#fde68a',
                fontFamily: 'monospace',
                fontSize: '0.92rem',
                fontWeight: 700
              }}>
                {respuestaChat.resumen_clase}
              </div>

              {respuestaChat.alerta_seguridad && (
                <div style={{
                  background: 'rgba(244, 63, 94, 0.14)',
                  border: '1.5px solid #f43f5e',
                  borderRadius: '14px',
                  padding: '1rem 1.2rem',
                  color: '#fecdd3',
                  fontSize: '0.9rem'
                }}>
                  <strong>🛡️ Defensa Activa (Revisión 3):</strong> {respuestaChat.alerta_seguridad}
                </div>
              )}

              <div style={{
                background: respuestaChat.abstencion ? 'rgba(244, 63, 94, 0.08)' : 'rgba(16, 185, 129, 0.1)',
                border: `1.5px solid ${respuestaChat.abstencion ? '#f43f5e' : '#10b981'}`,
                borderRadius: '16px',
                padding: '1.4rem'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.6rem' }}>
                  <strong style={{ color: respuestaChat.abstencion ? '#fb7185' : '#34d399', fontSize: '1.05rem' }}>
                    {respuestaChat.abstencion
                      ? `Modo Silencio / Derivación (${respuestaChat.tipo})`
                      : `Respuesta Fundamentada · Cita Verificada: ${respuestaChat.citas.join(', ')}`}
                  </strong>
                  <span style={{ fontSize: '0.8rem', color: '#9ca3af', fontFamily: 'monospace' }}>
                    Mejor distancia coseno: {respuestaChat.mejor_distancia.toFixed(2)} (umbral: {respuestaChat.umbral_distancia ?? 0.45})
                  </span>
                </div>
                <p style={{ color: '#f3f4f6', lineHeight: 1.6, margin: 0 }}>{respuestaChat.respuesta}</p>

                {respuestaChat.sancion_calculada && (
                  <div style={{
                    marginTop: '1rem',
                    background: 'rgba(0, 0, 0, 0.35)',
                    borderRadius: '12px',
                    padding: '1rem',
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                    gap: '0.75rem'
                  }}>
                    <div>
                      <span style={{ fontSize: '0.72rem', color: '#9ca3af', textTransform: 'uppercase' }}>Cálculo en Código (`calcular_sancion`)</span>
                      <div style={{ fontWeight: 800, color: '#f59e0b', fontSize: '1.15rem' }}>
                        ${respuestaChat.sancion_calculada.multa_usd.toFixed(2)} USD ({respuestaChat.sancion_calculada.porcentaje_sbu}% SBU)
                      </div>
                    </div>
                    <div>
                      <span style={{ fontSize: '0.72rem', color: '#9ca3af', textTransform: 'uppercase' }}>Puntos Texto COIP / Hoy</span>
                      <div style={{ fontWeight: 800, color: '#f43f5e', fontSize: '1.05rem' }}>
                        -{respuestaChat.sancion_calculada.puntos_texto_coip} pts (Hoy: -{respuestaChat.sancion_calculada.puntos_aplicables_hoy} pts)
                      </div>
                    </div>
                    <div>
                      <span style={{ fontSize: '0.72rem', color: '#9ca3af', textTransform: 'uppercase' }}>Código Tabla Oficial</span>
                      <div style={{ fontWeight: 700, color: '#fff', fontSize: '0.92rem' }}>
                        {respuestaChat.sancion_calculada.codigo_csv} · {respuestaChat.sancion_calculada.id_contravencion}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {respuestaChat.fragmentos.length > 0 && (
                <div style={{
                  background: 'rgba(31, 41, 55, 0.5)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '14px',
                  padding: '1.2rem'
                }}>
                  <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f59e0b', marginBottom: '0.75rem' }}>
                    Top-5 Vecinos Más Cercanos en ChromaDB (`where={'{"vigente": True}'}` · Modelo `{respuestaChat.modelo_embeddings || 'intfloat/multilingual-e5-small'}`)
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                    {respuestaChat.fragmentos.map((f) => (
                      <div
                        key={f.id}
                        style={{
                          background: f.puesto === 1 ? 'rgba(245, 158, 11, 0.1)' : 'rgba(17, 24, 39, 0.7)',
                          border: `1px solid ${f.puesto === 1 ? 'rgba(245, 158, 11, 0.4)' : 'rgba(255, 255, 255, 0.06)'}`,
                          borderRadius: '10px',
                          padding: '0.75rem 1rem',
                          fontSize: '0.86rem'
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700, color: '#fff', marginBottom: '0.25rem' }}>
                          <span>#{f.puesto} · {f.documento} — Art. {f.articulo} ({f.id})</span>
                          <span style={{ fontFamily: 'monospace', color: '#fbbf24' }}>
                            distancia coseno: {f.distancia.toFixed(2)} | vigente: {String(f.metadatos.vigente)}
                          </span>
                        </div>
                        <div style={{ color: '#9ca3af', fontSize: '0.82rem' }}>
                          {f.texto.slice(0, 220)}{f.texto.length > 220 ? '…' : ''}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
                gap: '1rem'
              }}>
                <div style={{
                  background: 'rgba(31, 41, 55, 0.5)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '14px',
                  padding: '1.1rem'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
                    <strong style={{ color: '#34d399', fontSize: '0.9rem' }}>Agente de Alcance Controlado</strong>
                    <span style={{ fontFamily: 'monospace', fontSize: '0.82rem', color: '#fbbf24' }}>
                      Vueltas: {respuestaChat.agente.vueltas_usadas} / {respuestaChat.agente.tope_vueltas}
                    </span>
                  </div>
                  {respuestaChat.agente.bitacora.map((b, idx) => (
                    <div key={idx} style={{ fontSize: '0.8rem', color: '#d1d5db', marginBottom: '0.45rem', borderLeft: '2px solid #10b981', paddingLeft: '0.6rem' }}>
                      <strong>Vuelta {b.vuelta} ({b.herramienta}):</strong> {b.detalle}
                    </div>
                  ))}
                </div>

                <div style={{
                  background: 'rgba(31, 41, 55, 0.5)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '14px',
                  padding: '1.1rem'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
                    <strong style={{ color: '#a78bfa', fontSize: '0.9rem' }}>Automatización Inteligente (4 Estaciones)</strong>
                    <span style={{ fontFamily: 'monospace', fontSize: '0.82rem', color: '#c4b5fd' }}>
                      Confianza: {(respuestaChat.automatizacion.confianza * 100).toFixed(0)}%
                    </span>
                  </div>
                  {respuestaChat.automatizacion.estaciones.map((st, idx) => (
                    <div key={idx} style={{ fontSize: '0.8rem', color: '#d1d5db', marginBottom: '0.45rem', borderLeft: '2px solid #8b5cf6', paddingLeft: '0.6rem' }}>
                      <strong>{st.estacion} [{st.actor}]:</strong> {st.resultado}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>
      )}

      <footer style={{
        marginTop: 'auto',
        borderTop: '1px solid rgba(255, 255, 255, 0.06)',
        paddingTop: '1.5rem',
        fontSize: '0.85rem',
        color: '#6b7280',
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        gap: '1rem'
      }}>
        <span>Simulador Vial «Vía Segura» · Escuela de Conducción UNIANDES · Octubre 2026</span>
        <span>Protección de Datos: Sesión anónima conforme a la LOPDP (Ecuador) · Cero recolección de PII</span>
      </footer>
    </div>
  );
}

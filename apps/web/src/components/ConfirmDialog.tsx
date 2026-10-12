import Modal from './Modal'

interface ConfirmDialogProps {
  title: string
  message: string
  pending?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmDialog({ title, message, pending, onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <Modal
      title={title}
      onClose={onCancel}
      width={420}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            Annuler
          </button>
          <button type="button" className="btn btn-danger" onClick={onConfirm} disabled={pending}>
            Supprimer
          </button>
        </>
      }
    >
      <p className="text-[13px] leading-relaxed text-muted">{message}</p>
    </Modal>
  )
}
